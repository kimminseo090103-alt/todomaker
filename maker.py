# file: todo_maker_maker.py
import streamlit as st
import sqlite3
from datetime import datetime

# DB 초기화
conn = sqlite3.connect("todo_points.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE, points INTEGER DEFAULT 0)""")
c.execute("""CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, points_reward INTEGER,
                completed INTEGER DEFAULT 0, created_at TEXT, completed_at TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY, name TEXT, cost INTEGER, description TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY, user_id INTEGER, reward_id INTEGER, purchased_at TEXT)""")
conn.commit()

# 초기 보상 데이터
def init_rewards():
    existing = c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0]
    if existing == 0:
        items = [("5분 휴식권", 15, "짧은 휴식으로 재충전하세요"),
                 ("간식권", 30, "작은 간식 한 개"),
                 ("30분 자유시간", 60, "집중 해제 시간")]
        c.executemany("INSERT INTO rewards (name,cost,description) VALUES (?,?,?)", items)
        conn.commit()
init_rewards()

st.title("할일로 포인트 모으기")
# 간단 로그인(닉네임)
if "user" not in st.session_state:
    name = st.text_input("닉네임을 입력하세요", value="사용자")
    if st.button("로그인"):
        c.execute("INSERT OR IGNORE INTO users (name, points) VALUES (?,?)", (name,0))
        conn.commit()
        user = c.execute("SELECT id,name,points FROM users WHERE name=?", (name,)).fetchone()
        st.session_state.user = {"id":user[0], "name":user[1], "points":user[2]}
        st.experimental_rerun()
else:
    user = st.session_state.user
    # 새 할일 추가
    st.sidebar.header("할일 추가")
    title = st.sidebar.text_input("할일 제목")
    reward = st.sidebar.number_input("완료 시 포인트", min_value=1, value=10)
    if st.sidebar.button("추가"):
        now = datetime.now().isoformat()
        c.execute("INSERT INTO todos (user_id,title,points_reward,created_at) VALUES (?,?,?,?)",
                  (user["id"], title, reward, now))
        conn.commit()
        st.sidebar.success("할일이 추가되었습니다.")

    # 사용자 최신 포인트 갱신
    row = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()
    st.session_state.user["points"] = row[0]

    st.subheader(f'안녕하세요, {user["name"]}님 — 포인트: {st.session_state.user["points"]}점')

    # 할일 리스트
    st.write("## 할일 목록")
    todos = c.execute("SELECT id,title,points_reward,completed FROM todos WHERE user_id=? ORDER BY id DESC",
                      (user["id"],)).fetchall()
    for t in todos:
        tid, ttitle, tpoints, tcompleted = t
        cols = st.columns([6,1,1])
        cols[0].markdown(f"- **{ttitle}** ({tpoints}점)")
        if tcompleted:
            cols[1].write("완료")
        else:
            if cols[1].button("완료", key=f"done_{tid}"):
                now = datetime.now().isoformat()
                c.execute("UPDATE todos SET completed=1, completed_at=? WHERE id=?", (now, tid))
                # 포인트 지급
                c.execute("UPDATE users SET points = points + ? WHERE id=?", (tpoints, user["id"]))
                conn.commit()
                st.success(f"{tpoints}점을 획득했습니다!")
                st.experimental_rerun()

    st.write("## 보상 샵")
    rewards = c.execute("SELECT id,name,cost,description FROM rewards").fetchall()
    for r in rewards:
        rid, name_r, cost, desc = r
        rcols = st.columns([4,1])
        rcols[0].write(f"**{name_r}** - {cost}점  \n{desc}")
        if rcols[1].button("구매", key=f"buy_{rid}"):
            # 잔액 확인
            points_now = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()[0]
            if points_now >= cost:
                c.execute("UPDATE users SET points = points - ? WHERE id=?", (cost, user["id"]))
                c.execute("INSERT INTO purchases (user_id,reward_id,purchased_at) VALUES (?,?,?)",
                          (user["id"], rid, datetime.now().isoformat()))
                conn.commit()
                st.success(f"{name_r}을(를) 구매했습니다.")
                st.experimental_rerun()
            else:
                st.error("포인트가 부족합니다.")

    st.write("## 구매 이력")
    hist = c.execute("""SELECT p.id, r.name, p.purchased_at FROM purchases p
                        JOIN rewards r ON p.reward_id = r.id WHERE p.user_id=?
                        ORDER BY p.purchased_at DESC""", (user["id"],)).fetchall()
    for h in hist:
        st.write(f"- {h[1]} — {h[2]}")
