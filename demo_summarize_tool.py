#!/usr/bin/env python3
#summarize the statistics of the boston cases from 2014 of unsolved homicides
#1
"""
Simple demonstration of how to use the summarize_boston_cases tool.
"""

import sys
import os

# Add the current directory to the path so we can import the tool
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the tool function directly
from cold_case_cross_checker import summarize_boston_cases

def main():
    """Demonstrate the summarize_boston_cases tool."""
    
    print("🧪 DEMONSTRATION: summarize_boston_cases Tool")
    print("=" * 60)
    print("This tool summarizes cases from the Boston Police 2014 unsolved homicides database.")
    print("It provides detailed analysis including individual case summaries and statistics.")
    print()
    
    print("🚀 Running the tool...")
    print("-" * 40)
    
    try:
        # Call the tool function directly
        result = summarize_boston_cases()
        print(result)
        
        print("\n" + "=" * 60)
        print("✅ Tool executed successfully!")
        
    except Exception as e:
        print(f"❌ Error running tool: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("📖 HOW TO USE THE NEW TOOL:")
    print("=" * 60)
    print()
    print("METHOD 1 - Direct Function Call (as shown below):")
    print("   from cold_case_cross_checker import summarize_boston_cases")
    print("   result = summarize_boston_cases()")
    print("   print(result)")
    print()
    print("METHOD 2 - Via MCP Server:")
    print("   1. Start the server: python cold_case_cross_checker.py")
    print("   2. Connect with an MCP client")
    print("   3. Call tool: summarize_boston_cases")
    print()
    print("METHOD 3 - Using the use_mcp_tool function:")
    print("   <use_mcp_tool>")
    print("   <server_name>ColdCaseCrossChecker</server_name>")
    print("   <tool_name>summarize_boston_cases</tool_name>")
    print("   <arguments>{}</arguments>")
    print("   </use_mcp_tool>")
    print()
    print("=" * 60)
    print()
    
    success = main()
    
    if success:
        print("\n🎉 Demonstration completed successfully!")
        print("\nThe tool is now ready to use in your cold case analysis workflow.")
    else:
        print("\n❌ Demonstration failed!")
        print("Please check the error messages above for troubleshooting.")
