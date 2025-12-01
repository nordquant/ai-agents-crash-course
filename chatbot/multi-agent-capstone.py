import chainlit as cl
import dotenv
import os
import chromadb
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, WebSearchTool, function_tool, trace, SQLiteSession
from agents.mcp import MCPServerStreamableHttp

from nutrition_agent import nutrition_agent

dotenv.load_dotenv()
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if (username, password) == (
        os.getenv("CHAINLIT_USERNAME"),
        os.getenv("CHAINLIT_PASSWORD"),
    ):
        return cl.User(
            identifier="Student",
            metadata={"role": "student", "provider": "credentials"},
        )
    else:
        return None
    
    
chroma_client = chromadb.PersistentClient(path="../chroma")
nutrition_db = chroma_client.get_collection(name="nutrition_db")

# This is the same code as in the rag.ipynb notebook

@function_tool
def calorie_lookup_tool(query: str, max_results: int = 3) -> str:
    """
    Tool function for a RAG database to look up calorie information for specific food items, but not for meals.

    Args:
        query: The food item to look up.
        max_results: The maximum number of results to return.

    Returns:
        A string containing the nutrition information.
    """

    results = nutrition_db.query(query_texts=[query], n_results=max_results)

    if not results["documents"][0]:
        return f"No nutrition information found for: {query}"

    # Format results for the agent
    formatted_results = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]
        food_item = metadata.get("food_item", "").title()
        calories = metadata.get("calories_per_100g", "unknown")
        category = metadata.get("food_category", "").title()

        formatted_results.append(
            f"{food_item} ({category}): {calories} calories per 100g"
        )

    return "Nutrition Information:\n" + "\n".join(formatted_results)


exa_search_mcp = MCPServerStreamableHttp(
    name="Exa Search MCP",
    params={
        # fixed nested quotes here
        "url": f"https://mcp.exa.ai/mcp?{os.environ.get('EXA_API_KEY', '')}",
        "timeout": 30,
    },
    client_session_timeout_seconds=30,
    cache_tools_list=True,
    max_retry_attempts=1,
)

# Note: connect() must be awaited inside an async context; moved into on_chat_start()

# First agent
calorie_agent_with_search = Agent(
    name="Nutrition Assistant",
    instructions="""
    * You are a helpful nutrition assistant giving out calorie information.
    * You give concise answers.
    * You follow this workflow:
        0) First, use the calorie_lookup_tool to get the calorie information of the ingredients. But only use the result if it's explicitly for the food requested in the query.
        1) If you couldn't find the exact match for the food or you need to look up the ingredients, search the EXA web to figure out the exact ingredients of the meal.
        Even if you have the calories in the web search response, you should still use the calorie_lookup_tool to get the calorie
        information of the ingredients to make sure the information you provide is consistent.
        2) Then, if necessary, use the calorie_lookup_tool to get the calorie information of the ingredients.
    * Even if you know the recipe of the meal, always use Exa Search to find the exact recipe and ingredients.
    * Once you know the ingredients, use the calorie_lookup_tool to get the calorie information of the individual ingredients.
    * If the query is about the meal, in your final output give a list of ingredients with their quantities and calories for a single serving. Also display the total calories.
    * Don't use the calorie_lookup_tool more than 10 times.
    """,
    tools=[calorie_lookup_tool],
    mcp_servers=[exa_search_mcp],
)

# 2nd Agent

healthy_breakfast_planner_agent = Agent(
    name="Breakfast Planner Assistant",
    instructions="""
    * You are a helpful assistant that helps with healthy breakfast choices.
    * You give concise answers.
    Given the user's preferences prompt, come up with different breakfast meals that are healthy and fit for a busy person.
    * Explicitly mention the meal's names in your response along with a sentence of why this is a healthy choice.
    """,
)

# 3rd and 4th agents

calorie_calculator_tool = calorie_agent_with_search.as_tool(
    tool_name="calorie-calculator",
    tool_description="Use this tool to calculate the calories of a meal and it's ingredients",
)

breakfast_planner_tool = healthy_breakfast_planner_agent.as_tool(
    tool_name="breakfast-planner",
    tool_description="Use this tool to plan a a number of healthy breakfast options",
)

breakfast_price_checker_agent = Agent(
    name="Breakfast Price Checker Assistant",
    instructions="""
    * You are a helpful assistant that takes multiple breakfast items (with ingredients and calories) and checks for the price of the ingredients.
    * Use the we search tool to get an approximate price for the ingredients.
    * In your final output prove the meal name, ingredients with calories and price for each meal.
    * Use markdown and be as concise as possible.
    """,
    tools=[WebSearchTool()],
)

breakfast_advisor = Agent(
    name="Breakfast Advisor",
    instructions="""
    * You are a breakfast advisor. You come up with meal plans for the user based on their preferences.
    * You also calculate the calories for the meal and its ingredients.
    * Based on the breakfast meals and the calories that you get from upstream agents,
    * Create a meal plan for the user. For each meal, give a name, the ingredients, and the calories

    Follow this workflow carefully:
    1) Use the breakfast_planner_tool to plan a a number of healthy breakfast options.
    2) Use the calorie_calculator_tool to calculate the calories for the meal and its ingredients.
    3) Handoff the breakfast meals and the calories to the Use the Breakfast Price Checker Assistant to add the prices in the last step.

    """,
    tools=[breakfast_planner_tool, calorie_calculator_tool],
    handoff_description="""
    Create a concise breakfast recommendation based on the user's preferences. Use Markdown format.
    """,
    handoffs=[breakfast_price_checker_agent],
)


@cl.on_chat_start
async def on_chat_start():
    # connect the MCP within an async function so `await` is valid
    try:
        await exa_search_mcp.connect()
    except Exception as e:
        # optionally log or print; keeping concise so agent can still run without MCP
        print(f"Warning: failed to connect to Exa MCP: {e}")

    session = SQLiteSession("conversation_history")
    cl.user_session.set("agent_session", session)


@cl.on_message
async def on_message(message: cl.Message):
    session = cl.user_session.get("agent_session")

    result = Runner.run_streamed(nutrition_agent, message.content, session=session)

    msg = cl.Message(content="")
    async for event in result.stream_events():
        # Stream final message text to screen
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            await msg.stream_token(token=event.data.delta)

        elif (
            event.type == "raw_response_event"
            and hasattr(event.data, "item")
            and hasattr(event.data.item, "type")
            and event.data.item.type == "function_call"
            and len(event.data.item.arguments) > 0
        ):
            with cl.Step(name=f"{event.data.item.name}", type="tool") as step:
                step.input = event.data.item.arguments

    await msg.update()