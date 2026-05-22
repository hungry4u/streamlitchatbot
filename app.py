import json
import streamlit as st
import anthropic

from database import init_db, execute_query, result_to_text, SCHEMA_INFO

init_db()

st.set_page_config(page_title="설비 DB 챗봇", page_icon="🏭", layout="centered")
st.title("🏭 설비 DB 챗봇")
st.caption("설비 정보에 대해 자연어로 질문하면 DB를 조회하여 답변합니다.")

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("설정")
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
    st.divider()
    st.subheader("DB 스키마")
    st.code(SCHEMA_INFO.strip(), language="text")
    st.divider()
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.rerun()

# ── 세션 상태 ─────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []  # {"role", "content", "sql"(optional)}

# ── 대화 이력 표시 ────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sql"):
            with st.expander("실행된 SQL"):
                st.code(msg["sql"], language="sql")

# ── LLM + Tool Use 쿼리 함수 ──────────────────────────────
TOOLS = [
    {
        "name": "execute_sql",
        "description": (
            "설비(equipment) 테이블에 SELECT 쿼리를 실행합니다. "
            "사용자의 질문에 답하기 위해 DB 조회가 필요할 때 이 도구를 사용하세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "실행할 SELECT SQL 쿼리",
                }
            },
            "required": ["sql"],
        },
    }
]

SYSTEM_PROMPT = f"""당신은 설비 데이터베이스를 조회해주는 한국어 챗봇입니다.
사용자가 설비에 관한 질문을 하면, execute_sql 도구를 사용해 데이터베이스를 조회하고
그 결과를 바탕으로 친절하고 명확하게 한국어로 답변하세요.

데이터베이스 스키마:
{SCHEMA_INFO}

규칙:
- 반드시 SELECT 쿼리만 사용하세요.
- 쿼리 결과를 기반으로 정확한 숫자와 사실을 답변에 포함하세요.
- 결과가 없을 경우 그 사실을 명확히 알려주세요.
- 쿼리와 무관한 일반 질문에는 도구 없이 직접 답변하세요.
"""


def ask_llm(user_question: str, history: list[dict], api_key: str):
    """
    Claude API Tool Use 방식으로 질문에 답변합니다.
    Returns (answer_text, executed_sql or None)
    """
    client = anthropic.Anthropic(api_key=api_key)

    # 이전 대화 이력을 메시지로 구성 (tool-use 없이 plain text만)
    messages = []
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_question})

    executed_sqls = []

    # Agentic loop: tool_use → execute → end_turn
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "execute_sql":
                    sql = block.input.get("sql", "")
                    executed_sqls.append(sql)
                    db_result = execute_query(sql)
                    result_text = result_to_text(db_result)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(
                                {
                                    "query_result": result_text,
                                    "raw": db_result,
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            combined_sql = "\n\n".join(executed_sqls) if executed_sqls else None
            return final_text, combined_sql

        else:
            return "응답 처리 중 오류가 발생했습니다.", None


# ── 채팅 입력 ─────────────────────────────────────────────
placeholder = "예) type이 normal인 설비 댓수 알려줘 / prod1을 생산하는 설비 목록 보여줘"
if prompt := st.chat_input(placeholder):
    if not api_key:
        st.warning("사이드바에서 Anthropic API Key를 먼저 입력해주세요.")
        st.stop()

    # 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 어시스턴트 응답
    with st.chat_message("assistant"):
        with st.spinner("DB를 조회하는 중..."):
            answer, sql = ask_llm(
                prompt,
                st.session_state.messages[:-1],  # 현재 질문 제외한 이력
                api_key,
            )
        st.markdown(answer)
        if sql:
            with st.expander("실행된 SQL"):
                st.code(sql, language="sql")

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sql": sql}
    )
