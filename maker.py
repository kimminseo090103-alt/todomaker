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
        st.warning("users 테이블에 created_at 컬럼 추가 시 문제가 발생했습니다: " + str(e))

init_db()

def init_rewards():
    existing = c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0]
    if existing == 0:
        items = [("5분 휴식권", 15, "짧은 휴식으로 재충전하세요"),
                 ("간식권", 30, "작은 간식 한 개"),
                 ("30분 자유시간", 60, "집중 해제
