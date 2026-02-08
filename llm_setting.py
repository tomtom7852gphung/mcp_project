from pydantic import BaseModel, Field
from typing import Optional
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
load_dotenv()
import os


user_setting = {"openai_api_version": os.getenv("OPENAI_API_VERSION"),
                "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
                "openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                "azure_deployment": os.getenv("AZURE_DEPLOYMENT")}
llm = AzureChatOpenAI(**user_setting , temperature = 0 , max_tokens = 4096)



class EmailAnalysis(BaseModel):
    category: str = Field(description = "分類：急件、一般、詢價、會議邀約、垃圾")
    priority: int = Field(description = "優先級評等 1-5")
    reasoning: str = Field(description = "詳細決策邏輯")
    suggested_reply: str = Field(description = "回覆草稿")