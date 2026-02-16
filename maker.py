# file: todo_points_app.py
import streamlit as st
import sqlite3
from datetime import datetime
import os

# ---------- 설정 ----------
DB_PATH = os.path.join(os.getcwd(), "todo_points.db")

# DB 연결 (스트림릿 환경에서 파일 쓰기 권한 확인)
def get_conn():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn
    except Exception as e:
        st.error("DB 연결 오류가 발생했습니다: " + str(e))
        st.stop()

conn = get_conn()
c = conn.cursor()

# ---------- DB 초기화 ----------
def init_db():
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT UNIQUE, 
                    points INTEGER DEFAULT 0,
                    created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER, 
                    title TEXT, 
                    points_reward INTEGER,
                    completed INTEGER DEFAULT 0, 
                    created_at TEXT, 
                    completed_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, 
                    cost INTEGER, 
                    description TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER, 
                    reward_id INTEGER, 
                    purchased_at TEXT)""")
    conn.commit()

def init_rewards():
    existing = c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0]
    if existing == 0:
        items = [("5분 휴식권", 15, "짧은 휴식으로 재충전하세요"),
                 ("간식권", 30, "작은 간식 한 개"),
                 ("30분 자유시간", 60, "집중 해제 시간")]
        c.executemany("INSERT INTO rewards (name,cost,description) VALUES (?,?,?)", items)
        conn.commit()

init_db()
init_rewards()

# ---------- 유틸 함수 ----------
def get_user_by_name(name):
    return c.execute("SELECT id,name,points FROM users WHERE name=?", (name,)).fetchone()

def create_user(name):
    try:
        now = datetime.now().isoformat()
        c.execute("INSERT INTO users (name, points, created_at) VALUES (?,?,?)", (name, 0, now))
        conn.commit()
        return get_user_by_name(name)
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        st.error("회원 생성 중 오류가 발생했습니다: " + str(e))
        return None

def update_user_points(user_id, delta):
    c.execute("UPDATE users SET points = points + ? WHERE id=?", (delta, user_id))
    conn.commit()

# ---------- UI ----------
st.title("할일로 포인트 모으기")

# 세션 초기화(안전)
if "user" not in st.session_state:
    st.session_state.user = None

# 좌측: 로그인 / 회원가입 선택
mode = st.sidebar.radio("모드 선택", ("로그인", "회원가입"))

if mode == "회원가입":
    st.sidebar.header("회원가입")
    new_name = st.sidebar.text_input("닉네임을 입력하세요", key="signup_name")
    if st.sidebar.button("회원가입"):
        if not new_name or new_name.strip() == "":
            st.sidebar.error("닉네임을 입력하세요.")
        else:
            # 이미 있는지 확인
            if get_user_by_name(new_name):
                st.sidebar.error("이미 존재하는 닉네임입니다. 다른 닉네임을 입력하세요.")
            else:
                user_row = create_user(new_name)
                if user_row:
                    st.sidebar.success("회원가입이 완료되었습니다. 자동으로 로그인됩니다.")
                    st.session_state.user = {"id": user_row[0], "name": user_row[1], "points": user_row[2]}
                    # 안전하게 페이지 갱신
                    st.experimental_rerun()

else:
    st.sidebar.header("로그인")
    name = st.sidebar.text_input("닉네임", key="login_name")
    if st.sidebar.button("로그인"):
        if not name or name.strip() == "":
            st.sidebar.error("닉네임을 입력하세요.")
        else:
            user_row = get_user_by_name(name)
            if user_row:
                st.session_state.user = {"id": user_row[0], "name": user_row[1], "points": user_row[2]}
                st.sidebar.success(f"{name}님, 로그인 되었습니다.")
                st.experimental_rerun()
            else:
                st.sidebar.error("등록된 사용자가 없습니다. 회원가입을 해주세요.")

# 로그인 후 화면
if st.session_state.user:
    user = st.session_state.user

    # 사용자 최신 포인트 갱신
    try:
        row = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()
        if row:
            st.session_state.user["points"] = row[0]
    except Exception as e:
        st.error("포인트 조회 중 오류: " + str(e))

    st.subheader(f'안녕하세요, {user["name"]}님 — 포인트: {st.session_state.user["points"]}점')

    # 사이드바: 할일 추가
    st.sidebar.header("할일 추가")
    title = st.sidebar.text_input("할일 제목", key="todo_title")
    reward = st.sidebar.number_input("완료 시 포인트", min_value=1, value=10, key="todo_reward")
    if st.sidebar.button("추가", key="add_todo"):
        if not title or title.strip() == "":
            st.sidebar.error("할일 제목을 입력하세요.")
        else:
            try:
                now = datetime.now().isoformat()
                c.execute("INSERT INTO todos (user_id,title,points_reward,created_at) VALUES (?,?,?,?)",
                          (user["id"], title.strip(), reward, now))
                conn.commit()
                st.sidebar.success("할일이 추가되었습니다.")
                st.experimental_rerun()
            except Exception as e:
                st.sidebar.error("할일 추가 중 오류가 발생했습니다: " + str(e))

    # 할일 목록
    st.write("## 할일 목록")
    try:
        todos = c.execute("SELECT id,title,points_reward,completed FROM todos WHERE user_id=? ORDER BY id DESC",
                          (user["id"],)).fetchall()
    except Exception as e:
        st.error("할일 불러오기 중 오류: " + str(e))
        todos = []

    for t in todos:
        tid, ttitle, tpoints, tcompleted = t
        cols = st.columns([6,1,1])
        cols[0].markdown(f"- **{ttitle}** ({tpoints}점)")
        if tcompleted:
            cols[1].write("완료")
        else:
            if cols[1].button("완료", key=f"done_{tid}"):
                try:
                    now = datetime.now().isoformat()
                    c.execute("UPDATE todos SET completed=1, completed_at=? WHERE id=?", (now, tid))
                    update_user_points(user["id"], tpoints)
                    conn.commit()
                    st.success(f"{tpoints}점을 획득했습니다!")
                    # 포인트가 변경되었으니 갱신 후 rerun
                    st.experimental_rerun()
                except Exception as e:
                    st.error("작업 완료 처리 중 오류가 발생했습니다: " + str(e))

    # 보상 샵
    st.write("## 보상 샵")
    try:
        rewards = c.execute("SELECT id,name,cost,description FROM rewards").fetchall()
    except Exception as e:
        st.error("보상 불러오기 오류: " + str(e))
        rewards = []

    for r in rewards:
        rid, name_r, cost, desc = r
        rcols = st.columns([4,1])
        rcols[0].write(f"**{name_r}** - {cost}점  \n{desc}")
        if rcols[1].button("구매", key=f"buy_{rid}"):
            try:
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
            except Exception as e:
                st.error("구매 처리 중 오류가 발생했습니다: " + str(e))

    # 구매 이력
    st.write("## 구매 이력")
    try:
        hist = c.execute("""SELECT p.id, r.name, p.purchased_at FROM purchases p
                            JOIN rewards r ON p.reward_id = r.id WHERE p.user_id=?
                            ORDER BY p.purchased_at DESC""", (user["id"],)).fetchall()
    except Exception as e:
        st.error("구매 이력 조회 중 오류: " + str(e))
        hist = []

    for h in hist:
        st.write(f"- {h[1]} — {h[2]}")

    # 로그아웃 버튼
    if st.button("로그아웃"):
        st.session_state.user = None
        st.experimental_rerun()

else:
    st.info("왼쪽 사이드바에서 로그인 또는 회원가입을 해주세요.")
