# file: todo_points_app.py
import streamlit as st
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.getcwd(), "todo_points.db")

def get_conn():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn
    except Exception as e:
        st.error("DB 연결 오류가 발생했습니다: " + str(e))
        st.stop()

conn = get_conn()
c = conn.cursor()

# 컬럼 존재 여부 확인 유틸
def has_column(table, column):
    cols = c.execute(f"PRAGMA table_info('{table}')").fetchall()
    col_names = [r[1] for r in cols]
    return column in col_names

def init_db():
    # 기본 테이블 생성(없으면)
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT UNIQUE, 
                    points INTEGER DEFAULT 0
                 )""")

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

    # 마이그레이션: users 테이블에 created_at 컬럼이 없으면 추가
    try:
        if not has_column("users", "created_at"):
            c.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
            conn.commit()
    except Exception as e:
        # ALTER 실패 시 사용자에게 안내 (보통 권한 문제 아니면 잘 동작함)
        st.warning("users 테이블에 created_at 컬럼 추가 시 문제가 발생했습니다: " + str(e))

init_db()

def init_rewards():
    existing = c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0]
    if existing == 0:
        items = [("5분 휴식권", 15, "짧은 휴식으로 재충전하세요"),
                 ("간식권", 30, "작은 간식 한 개"),
                 ("30분 자유시간", 60, "집중 해제 시간")]
        c.executemany("INSERT INTO rewards (name,cost,description) VALUES (?,?,?)", items)
        conn.commit()
init_rewards()

# 이후는 이전에 드린 UI/로직과 동일
st.title("할일로 포인트 모으기")

if "user" not in st.session_state:
    st.session_state.user = None

mode = st.sidebar.radio("모드 선택", ("로그인", "회원가입"))

def get_user_by_name(name):
    return c.execute("SELECT id,name,points FROM users WHERE name=?", (name,)).fetchone()

def create_user(name):
    try:
        now = datetime.now().isoformat()
        # created_at 컬럼이 추가되어 있으면 같이 넣고, 없으면 컬럼 없이 INSERT 수행
        if has_column("users", "created_at"):
            c.execute("INSERT INTO users (name, points, created_at) VALUES (?,?,?)", (name, 0, now))
        else:
            c.execute("INSERT INTO users (name, points) VALUES (?,?)", (name, 0))
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

if mode == "회원가입":
    st.sidebar.header("회원가입")
    new_name = st.sidebar.text_input("닉네임을 입력하세요", key="signup_name")
    if st.sidebar.button("회원가입"):
        if not new_name or new_name.strip() == "":
            st.sidebar.error("닉네임을 입력하세요.")
        else:
            if get_user_by_name(new_name):
                st.sidebar.error("이미 존재하는 닉네임입니다. 다른 닉네임을 입력하세요.")
            else:
                user_row = create_user(new_name)
                if user_row:
                    st.sidebar.success("회원가입이 완료되었습니다. 자동으로 로그인됩니다.")
                    st.session_state.user = {"id": user_row[0], "name": user_row[1], "points": user_row[2]}
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

if st.session_state.user:
    user = st.session_state.user
    try:
        row = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()
        if row:
            st.session_state.user["points"] = row[0]
    except Exception as e:
        st.error("포인트 조회 중 오류: " + str(e))

    st.subheader(f'안녕하세요, {user["name"]}님 — 포인트: {st.session_state.user["points"]}점')

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
                st
