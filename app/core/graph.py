from typing import Optional, List, TypedDict, Any
from openai import OpenAI
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import StateGraph, START, END
import json
import copy

class GraphState(TypedDict):
    query: str  # 사용자의 질의
    final_answer: Optional[str]  # GPT의 최종 응답
    history: List[dict]  # 이전 대화 내역
    update: List[dict]  # 이번 세션에서 생성된 메시지 (tool_call, tool 응답 등)



class CancerRagAgent:
    """
    질문이 들어왔을 때, 벡터DB에 관련 문서 검색 후 이를 바탕으로 답변하는 RAG
    """
    def __init__(self, client: OpenAI, retriever_cancer: BaseRetriever):
        self.client = client
        self.retriever_cancer = retriever_cancer
        self._graph = None


    # Function calling 노드 
    async def function_call(self, state: GraphState) -> dict:
        """
        GPT Function Calling을 활용, 질문이 들어왔을 때 이전 맥락 + 멀티 쿼리를 고려하여 질문을 분할하고, 
        적절한 함수(Document 검색)가 호출되도록 유도
        
        """
        # 시스템 프롬프트
        system_message = {"role": "system", "content": "너는 암 관련 정보를 제공하는 전문가야."}

        # 기존 히스토리 + 현재 질문을 messages로 구성
        messages = [system_message] + state["history"] + [
            {"role": "user", "content": state["query"]}
        ]
        # 함수 명세
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_cancer_info",
                    "description": "암 관련 정보를 벡터 검색을 통해 제공합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "검색할 질의 내용 (예: '대장암 초기 증상')"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        response =  await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message


        # GPT tool_call 메시지를 히스토리에 추가(state['update'])
        updated_history = [
            {"role": "user", "content": state["query"]},  # 현재 질문
            assistant_message.model_dump()  # assistant의 tool_call 응답
        ]
        
        return {
            **state,
            "update": updated_history
        }

    # 문서 검색기
    async def search_cancer_info(self, query: str) -> str:
        """
        앞서 생성한 retreiver를 활용, 질문과 관련있는 문서를 추출
        """
        docs = await self.retriever_cancer.aget_relevant_documents(query)
        return "\n\n".join([doc.page_content for doc in docs])

    # 함수 실행 기능(아래 excute_function_process 노드에서 사용되어짐)
    async def execute_function(self, function_name: str, arguments: dict) -> str:
        """
        Function Calling을 통해 추출된 함수 이름과 인자를 기반으로 실제 함수를 실행하는 노드

        Args:
            function_name (str): 실행할 함수의 이름 (예: "search_cancer_info")
            arguments (dict): 해당 함수에 전달할 인자들 (예: {"query": "대장암 증상"})

        Returns:
            str: 실행된 함수의 결과 문자열 (예: 검색된 문서 내용)
        """
        # 함수 매핑
        function_map = {
            "search_cancer_info": self.search_cancer_info
        }
        if function_name not in function_map:
            return f"Error: Function '{function_name}' not found"

        # 해당 함수 실행
        return await function_map[function_name](**arguments)
 

    #function calling 기반, 함수 실행
    async def excute_function_process(self, state: GraphState) -> GraphState:
        """
        GPT로부터 받은 tool_call 정보를 기반으로 실제 함수를 실행하고, 그 결과를 LangGraph 상태의 update 메시지에 추가하는 노드

        Args:
            state (GraphState): LangGraph의 현재 상태로, 이전 대화 내용과 tool_call 정보 등을 포함

        Returns:
            dict: 함수 실행 결과가 반영된 새로운 상태 (GraphState)
    """
        messages = state['update']
        assistant_message = messages[-1]  # dict 타입

        # 모든 함수 호출 수행
        for tool_call in assistant_message.get("tool_calls", []):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
       

  
            # 함수 실행 결과 가져오기
            function_response = await self.execute_function(function_name, function_args)
            
    

            # 실행 결과를 update에 저장
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call['id'],
                "name": function_name,
                "content": json.dumps(function_response, ensure_ascii=False)
            })

        return {
            **state,
            "update": messages
            }


    # 답변 바탕으로, tools 사용 여부 분기 처리
    async def should_continue(self, state: GraphState) -> str:
        """
        직전 GPT 응답 메시지에 tool_call이 포함되어 있는지를 확인하고, 이를 기반으로 LangGraph의 흐름을 분기

        Args:
            state (GraphState): LangGraph의 현재 상태 (update에는 최근 GPT 응답 포함)

        Returns:
            str: 다음 노드의 이름 ("tools" 또는 END)
                - "tools": 도구 호출 감지 → excute_function_process 노드로 이동
                - END: 도구 호출 없음 → 그래프 종료

        처리 순서:
            1. state["update"]에서 가장 마지막 메시지를 가져옴.
            2. 해당 메시지에 "tool_calls"가 존재하는지 확인.
            3. 존재하면 "tools"를 반환하여 함수 실행 노드로 이동하게 하고, 없으면 대화 흐름을 종료(END).
         """
        
        messages = state.get("update", [])
        if not messages:
            print("[should_continue] 메시지가 없어 종료합니다.")
            return END

        last_message = messages[-1]
        
        tool_calls = last_message.get("tool_calls", [])
    
        if tool_calls:
            print("[should_continue] 도구 호출 감지:", tool_calls)
            return "tools"

        return "end"


    async def final_response(self, state: GraphState) -> GraphState:
        """
    Function Calling 및 도구 실행이 완료된 후, 전체 대화 흐름(history + update)을 기반으로 최종 assistant 응답을 생성하는 노드

    Args:
        state (GraphState): LangGraph의 상태. 이전 history와 최신 update를 포함

    Returns:
        GraphState: 최종 assistant 응답과 update 목록, 최종 텍스트 답변이 포함된 상태 반환.
    """
        history = state.get("history") or []
        update = state.get("update") or []
        messages = history + update

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        assistant_message = response.choices[0].message

        final_answer = assistant_message.content  

        # update 리스트 복사 후 assistant_message 추가
        new_update = copy.deepcopy(state.get("update", []))
        new_update.append(assistant_message)
        
        return {
            **state,
            "update": new_update,
            "final_answer": final_answer
        }


    async def create_graph(self):
        """
        LangGraph 워크플로우 생성 및 컴파일
        """
        if self._graph is None:
            try:
                graph_builder = StateGraph(GraphState)

                # 🔹 노드 등록
                graph_builder.add_node("function_call", self.function_call)
                graph_builder.add_node("excute_function_process", self.excute_function_process)
                graph_builder.add_node("final_response", self.final_response)

                # ✅ 시작 지점 지정 (START → function_call)
                graph_builder.add_edge(START, "function_call")

                # 🔸 조건부 분기 설정: function_call → should_continue 판단
                graph_builder.add_conditional_edges(
                    "function_call",
                    self.should_continue,
                    {
                        "tools": "excute_function_process",  # tool_call 존재 시
                        "end": END                            # 종료
                    }
                )

                # 🔸 함수 실행 → 최종 응답
                graph_builder.add_edge("excute_function_process", "final_response")

                # 🔚 최종 응답 후 종료
                graph_builder.add_edge("final_response", END)

                # ✅ 컴파일
                self._graph = graph_builder.compile()
                print("[create_graph] LangGraph 그래프 컴파일 완료")

            except Exception as e:
                print(f"[create_graph] 그래프 생성 실패: {e}")
                self._graph = None

        return self._graph

    async def get_response(self, initial_state: GraphState) -> GraphState | list[dict]:
        """
        GPT 기반 LangGraph 실행하여 응답 생성

        Args:
            initial_state (dict): LangGraph에 전달할 초기 상태 (예: {"query": ..., "messages": ..., ...})

        Returns:
            GraphState | list[dict]: 실행 후의 상태 (도구 실행 결과 및 최종 응답 포함) 또는 빈 리스트 (실패 시)
        """
        # 그래프가 생성되지 않았다면 생성
        if self._graph is None:
            self._graph = await self.create_graph()

        # LangGraph 실행
        try:
            result_state: GraphState = await self._graph.ainvoke(initial_state)
            
            return result_state
        except Exception as e:
            print(f"[get_response] LangGraph 실행 실패: {e}")
            return []
