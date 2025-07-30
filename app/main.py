from fastapi import FastAPI
from app.routers import router
from app.core.config import config
from openai import OpenAI
from openai import AsyncOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    faiss_save_path = config.FAISS
    embedding_model = OpenAIEmbeddings(openai_api_key=config.OPENAI_API_KEY)
    vectorstore = FAISS.load_local(
        faiss_save_path,
        embedding_model,
        allow_dangerous_deserialization=True
    )

    app.state.openai_client = openai_client
    app.state.vectorstore = vectorstore


app.include_router(router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

