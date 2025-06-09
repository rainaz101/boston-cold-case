#4
import asyncio
import os
from typing import Optional, List
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv
from anthropic import Anthropic
import mcp.types as types

# Load environment variables
load_dotenv()

class SSE_MCP_Client:
    """
    Client for connecting to an MCP server using SSE.
    """
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None

    async def connect_to_server(self, server_url: str):
        """Connects to an MCP server via SSE."""
        try:
            sse_transport = await self.exit_stack.enter_async_context(sse_client(server_url))
            sse_recv, sse_sent = sse_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(sse_recv, sse_sent))
            if self.session:
                await self.session.initialize()
                print(f"Connected to MCP server at {server_url}")
        except Exception as e:
            print(f"Failed to connect to server: {e}")

    async def get_tools(self) -> List[types.Tool]:
        """Retrieves available tools from the server."""
        if not self.session:
            print("Session not initialized. Cannot retrieve tools.")
            return []
        response = await self.session.list_tools()
        print("Available tools:", [tool.name for tool in response.tools])
        return response.tools

    async def cleanup(self):
        """Closes the connection and cleans up resources."""
        await self.exit_stack.aclose()


def reformat_tools_for_anthropic(tools: List[types.Tool]):
    """
    Reformats the tool descriptions for Anthropic compatibility.
    """
    return [{
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema,
    } for tool in tools]


def check_tool_call(response):
    """
    Checks if the response contains a tool call.
    """
    try:
        if response.stop_reason == "tool_use":
            return response.content[1]  # Assuming response.content format is [chat_message, tool_call]
        return False
    except Exception as e:
        print(f"Error checking tool call: {e}")
        return None


async def main():
    client = SSE_MCP_Client()
    chat = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model_name = "claude-3-5-sonnet-20241022"  # Using standard Anthropic model
    print(f"Using model: {model_name}")
    
    try:
        await client.connect_to_server("http://localhost:5553/sse")
        tools = await client.get_tools()
        formatted_tools = reformat_tools_for_anthropic(tools)

        messages = []
        user_message = input("Input: ")

        # Create initial message
        chat_prompt = "You are a helpful assistant, you have the ability to call tools to achieve user requests.\n\n"
        chat_prompt += "User request: " + user_message + "\n\n"
        messages.append({"role": "user", "content": chat_prompt}) # passing in as user message

        while True:
            if not user_message:
                continue

            # Generate a response from the User Message
            llm_response = chat.messages.create(
                model=model_name,
                max_tokens=2048,
                messages=messages,
                tools=formatted_tools
            )
            llm_text_response = llm_response.content[0].text.strip()
            print(f"LLM Response: {llm_text_response}")
            messages.append({"role": "assistant", "content": llm_text_response})


            while (tool_call := check_tool_call(llm_response)):
                # Get a response from the Tool
                tool_response = await client.session.call_tool(tool_call.name, tool_call.input)
                tool_result_text = tool_response.content[0].text.strip()
                print(f"Tool Response: {tool_result_text}")

                messages.append({"role": "user", "content": f"Tool result: {tool_result_text}"})

                # Give the tool response to the LLM to create a final response to the User
                llm_response = chat.messages.create(
                    model=model_name,
                    max_tokens=2048,
                    messages=messages,
                    tools=formatted_tools,
                    temperature=0.1
                )
                llm_text_response = llm_response.content[0].text.strip()
                print(f"LLM: {llm_text_response}")
                messages.append({"role": "assistant", "content": llm_text_response})

            user_message = input("Input: ")
            messages.append({"role": "user", "content": user_message})

    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
