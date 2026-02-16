# file: todo_points_app.py
import streamlit as st
import sqlite3
from datetime import datetime
import os
import traceback
import sys
import time

# ---------- 설정 ----------
DB_FILENAME = "todo_points.db"
DB_PATH = os.path.join(os.getcwd(), DB_FILENAME)

# ---------- 안전한 재실행 유틸 ----------
def safe_rerun():
    try:
        if hasattr(st, "experimental_rerun"):
            try:
                st.experimental_rerun()
                return
            except Exception:
                pass
        if hasattr(st, "experimental_set_query_params"):
            st.experimental_set_query_params(_rerun=int(time.time() * 1000))
            return
    except Exception:
        pass
    st.session_state["_force_rerun"] = not st.session_state.get("_force_rerun", False)

# ---------- 앱 본문 ----------
def run_app():
    # DB 연결
    def get_conn(path=DB_PATH):
        try:
            conn = sqlite3.connect(path, check_same_thread=False)
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

    # DB 초기화 및 마이그레이션
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
                        description TEXT
                     )""")

        c.execute("""CREATE TABLE IF NOT EXISTS purchases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        reward_id INTEGER,
                        purchased_at TEXT)""")
        conn.commit()

        # users.created_at 컬럼이 없으면 추가
        try:
            if not has_column("users", "created_at"):
                c.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
                conn.commit()
        except Exception as e:
            st.warning("users 테이블 마이그레이션 경고: " + str(e))

        # rewards.stock 컬럼이 없으면 추가 (기존 DB에 컬럼이 없을 때 대비)
        try:
            if not has_column("rewards", "stock"):
                c.execute("ALTER TABLE rewards ADD COLUMN stock INTEGER DEFAULT -1")
                conn.commit()
        except Exception as e:
            st.warning("rewards 테이블에 stock 컬럼 추가 중 경고: " + str(e))

    init_db()

    # 초기 보상 데이터(한 번만)
    def init_rewards():
        try:
            existing = c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0]
            if existing == 0:
                items = [
                    ("5분 휴식권", 15, "짧은 휴식으로 재충전하세요", -1),
                    ("간식권", 30, "작은 간식을 받을 수 있는 쿠폰", 10),
                    ("30분 자유시간", 60, "집중 해제 시간", 5),
                ]
                # INSERT 문은 컬럼 수가 변경되었을 수 있으니 컬럼명 명시
                c.executemany("INSERT INTO rewards (name,cost,description,stock) VALUES (?,?,?,?)", items)
                conn.commit()
        except Exception as e:
            st.warning("초기 보상 데이터 삽입 중 오류: " + str(e))

    init_rewards()

    # 유틸 함수들
    def get_user_by_name(name):
        return c.execute("SELECT id,name,points FROM users WHERE name=?", (name,)).fetchone()

    def create_user(name):
        try:
            now = datetime.now().isoformat()
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

    def add_reward(name, cost, description, stock):
        try:
            c.execute("INSERT INTO rewards (name,cost,description,stock) VALUES (?,?,?,?)",
                      (name, cost, description, stock))
            conn.commit()
            return True
        except Exception as e:
            st.error("보상 추가 중 오류: " + str(e))
            return False

    def update_reward(rid, name, cost, description, stock):
        try:
            # 컬럼이 존재하지 않을 가능성 대비: 만약 stock 컬럼이 없으면 stock 업데이트는 무시
            if has_column("rewards", "stock"):
                c.execute("UPDATE rewards SET name=?, cost=?, description=?, stock=? WHERE id=?",
                          (name, cost, description, stock, rid))
            else:
                c.execute("UPDATE rewards SET name=?, cost=?, description=? WHERE id=?",
                          (name, cost, description, rid))
            conn.commit()
            return True
        except Exception as e:
            st.error("보상 수정 중 오류: " + str(e))
            return False

    def delete_reward(rid):
        try:
            c.execute("DELETE FROM rewards WHERE id=?", (rid,))
            conn.commit()
            return True
        except Exception as e:
            st.error("보상 삭제 중 오류: " + str(e))
            return False

    # UI 시작
    st.set_page_config(page_title="할일로 포인트 모으기", layout="wide")
    st.title("할일로 포인트 모으기")

    # 세션 초기화
    if "user" not in st.session_state:
        st.session_state.user = None
    if "_force_rerun" not in st.session_state:
        st.session_state["_force_rerun"] = False

    # 사이드바: 계정 + 보상 관리
    st.sidebar.markdown("## 계정")
    mode = st.sidebar.radio("모드 선택", ("로그인", "회원가입"))

    if mode == "회원가입":
        st.sidebar.header("회원가입")
        new_name = st.sidebar.text_input("닉네임을 입력하세요", key="signup_name")
        if st.sidebar.button("회원가입"):
            if not new_name or new_name.strip() == "":
                st.sidebar.error("닉네임을 입력하세요.")
            else:
                if get_user_by_name(new_name.strip()):
                    st.sidebar.error("이미 존재하는 닉네임입니다.")
                else:
                    user_row = create_user(new_name.strip())
                    if user_row:
                        st.sidebar.success("회원가입 완료 — 자동 로그인됩니다.")
                        st.session_state.user = {"id": user_row[0], "name": user_row[1], "points": user_row[2]}
                        safe_rerun()
                    else:
                        st.sidebar.error("회원가입 실패")

    else:
        st.sidebar.header("로그인")
        name = st.sidebar.text_input("닉네임", key="login_name")
        if st.sidebar.button("로그인"):
            if not name or name.strip() == "":
                st.sidebar.error("닉네임을 입력하세요.")
            else:
                user_row = get_user_by_name(name.strip())
                if user_row:
                    st.session_state.user = {"id": user_row[0], "name": user_row[1], "points": user_row[2]}
                    st.sidebar.success(f"{name.strip()}님, 로그인되었습니다.")
                    safe_rerun()
                else:
                    st.sidebar.error("등록된 사용자가 없습니다. 회원가입 해주세요.")

    # 보상 관리(사이드바)
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 보상 관리 (직접 설정)")
    with st.sidebar.expander("새 보상 추가"):
        rn = st.text_input("보상 이름", key="r_name")
        rc = st.number_input("필요 포인트", min_value=0, value=10, key="r_cost")
        rd = st.text_input("설명", key="r_desc")
        rs = st.number_input("수량 (무제한:-1)", value=-1, key="r_stock")
        if st.button("보상 추가", key="add_reward_btn"):
            if not rn or rn.strip() == "":
                st.sidebar.error("보상 이름을 입력하세요.")
            else:
                ok = add_reward(rn.strip(), int(rc), rd.strip(), int(rs))
                if ok:
                    st.sidebar.success("보상이 추가되었습니다.")
                    safe_rerun()

    # 보상 목록 편집 (사이드바)
    try:
        rewards_for_edit = c.execute("SELECT id,name,cost,description,stock FROM rewards ORDER BY id").fetchall()
    except Exception:
        # 만약 stock 컬럼이 없으면 stock 없이 가져오기
        rewards_for_edit = c.execute("SELECT id,name,cost,description FROM rewards ORDER BY id").fetchall()
        # 변환: 튜플 길이를 맞추기 위해 stock을 None으로 채움
        rewards_for_edit = [r + (None,) if len(r) == 4 else r for r in rewards_for_edit]

    if rewards_for_edit:
        with st.sidebar.expander("보상 목록 수정/삭제"):
            for r in rewards_for_edit:
                rid, rname, rcost, rdesc, rstock = r
                cols = st.columns([2,1,1])
                cols[0].markdown(f"**{rname}**")
                if cols[1].button("편집", key=f"edit_{rid}"):
                    st.session_state[f"edit_{rid}"] = True
                if cols[2].button("삭제", key=f"del_{rid}"):
                    if delete_reward(rid):
                        st.sidebar.success("삭제되었습니다.")
                        safe_rerun()
                if st.session_state.get(f"edit_{rid}", False):
                    with st.form(key=f"form_{rid}"):
                        iname = st.text_input("이름", value=rname, key=f"iname_{rid}")
                        icost = st.number_input("포인트", min_value=0, value=rcost, key=f"icost_{rid}")
                        idesc = st.text_input("설명", value=rdesc, key=f"idesc_{rid}")
                        istock = st.number_input("수량 (-1=무제한)", value=(rstock if rstock is not None else -1), key=f"istock_{rid}")
                        submitted = st.form_submit_button("저장")
                        if submitted:
                            if update_reward(rid, iname.strip(), int(icost), idesc.strip(), int(istock)):
                                st.success("수정 완료")
                                st.session_state[f"edit_{rid}"] = False
                                safe_rerun()

    # 로그인 후 메인 화면
    if st.session_state.user:
        user = st.session_state.user
        try:
            row = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()
            if row:
                st.session_state.user["points"] = row[0]
        except Exception as e:
            st.error("포인트 조회 오류: " + str(e))

        # 상단: 사용자 정보 및 포인트(코인) 표시
        col1, col2 = st.columns([3,1])
        col1.subheader(f'안녕하세요, {user["name"]}님')
        col2.metric("코인(포인트)", st.session_state.user["points"])

        # 좌측/우측 레이아웃: 미션 탭 + 보상 샵
        left, right = st.columns([3,2])

        # 왼쪽: 할일(진행중 / 완료 탭)
        with left:
            tab = st.tabs(["진행중", "완료"])
            # 진행중
            with tab[0]:
                st.write("### 진행중 미션")
                try:
                    todos_inprogress = c.execute(
                        "SELECT id,title,points_reward,created_at FROM todos WHERE user_id=? AND completed=0 ORDER BY id DESC",
                        (user["id"],)
                    ).fetchall()
                except Exception as e:
                    st.error("미션 불러오기 오류: " + str(e))
                    todos_inprogress = []

                if todos_inprogress:
                    for t in todos_inprogress:
                        tid, ttitle, tpoints, tcreated = t
                        row = st.columns([6,1,1])
                        row[0].markdown(f"- **{ttitle}** ({tpoints}점)")
                        if row[1].button("완료", key=f"done_{tid}"):
                            try:
                                now = datetime.now().isoformat()
                                c.execute("UPDATE todos SET completed=1, completed_at=? WHERE id=?", (now, tid))
                                update_user_points(user["id"], tpoints)
                                conn.commit()
                                st.success(f"{tpoints}점을 획득했습니다!")
                                safe_rerun()
                            except Exception as e:
                                st.error("완료 처리 오류: " + str(e))
                        if row[2].button("삭제", key=f"deltodo_{tid}"):
                            try:
                                c.execute("DELETE FROM todos WHERE id=?", (tid,))
                                conn.commit()
                                st.info("미션이 삭제되었습니다.")
                                safe_rerun()
                            except Exception as e:
                                st.error("삭제 오류: " + str(e))
                else:
                    st.info("진행중인 미션이 없습니다. 사이드바에서 추가해보세요.")

            # 완료
            with tab[1]:
                st.write("### 완료된 미션")
                try:
                    todos_done = c.execute(
                        "SELECT id,title,points_reward,completed_at FROM todos WHERE user_id=? AND completed=1 ORDER BY completed_at DESC",
                        (user["id"],)
                    ).fetchall()
                except Exception as e:
                    st.error("완료된 미션 불러오기 오류: " + str(e))
                    todos_done = []

                if todos_done:
                    for t in todos_done:
                        tid, ttitle, tpoints, tcomp = t
                        row = st.columns([6,1])
                        row[0].markdown(f"- **{ttitle}** ({tpoints}점) — 완료: {tcomp}")
                        if row[1].button("삭제", key=f"del_done_{tid}"):
                            try:
                                c.execute("DELETE FROM todos WHERE id=?", (tid,))
                                conn.commit()
                                st.info("완료된 미션이 삭제되었습니다.")
                                safe_rerun()
                            except Exception as e:
                                st.error("삭제 오류: " + str(e))
                else:
                    st.info("아직 완료된 미션이 없습니다.")

        # 오른쪽: 보상 샵 및 구매 이력
        with right:
            st.write("## 보상 샵 (구매하려면 클릭)")
            try:
                # rewards 테이블에 stock 컬럼이 없을 수 있으니 안전하게 읽기
                try:
                    rewards = c.execute("SELECT id,name,cost,description,stock FROM rewards ORDER BY id").fetchall()
                except Exception:
                    rewards = c.execute("SELECT id,name,cost,description FROM rewards ORDER BY id").fetchall()
                    rewards = [r + (None,) if len(r) == 4 else r for r in rewards]
            except Exception as e:
                st.error("보상 불러오기 오류: " + str(e))
                rewards = []

            for r in rewards:
                rid, name_r, cost, desc, stock = r
                stock_text = "무제한" if stock == -1 else ("재고: 없음" if stock == 0 else f"{stock}개")
                rcols = st.columns([4,1])
                rcols[0].write(f"**{name_r}** - {cost}점  \n{desc}  \n{stock_text}")
                if rcols[1].button("구매", key=f"buy_{rid}"):
                    try:
                        points_now = c.execute("SELECT points FROM users WHERE id=?", (user["id"],)).fetchone()[0]
                        if points_now >= cost:
                            if stock is None or stock == -1 or stock > 0:
                                c.execute("UPDATE users SET points = points - ? WHERE id=?", (cost, user["id"]))
                                c.execute("INSERT INTO purchases (user_id,reward_id,purchased_at) VALUES (?,?,?)",
                                          (user["id"], rid, datetime.now().isoformat()))
                                if stock is not None and stock > 0:
                                    c.execute("UPDATE rewards SET stock = stock - 1 WHERE id=?", (rid,))
                                conn.commit()
                                st.success(f"{name_r}을(를) 구매했습니다.")
                                safe_rerun()
                            else:
                                st.error("해당 보상은 재고가 없습니다.")
                        else:
                            st.error("포인트가 부족합니다.")
                    except Exception as e:
                        st.error("구매 처리 오류: " + str(e))

            st.markdown("---")
            st.write("## 구매 이력")
            try:
                hist = c.execute("""SELECT p.id, r.name, p.purchased_at FROM purchases p
                                    JOIN rewards r ON p.reward_id = r.id WHERE p.user_id=?
                                    ORDER BY p.purchased_at DESC""", (user["id"],)).fetchall()
            except Exception as e:
                st.error("구매 이력 조회 오류: " + str(e))
                hist = []

            if hist:
                for h in hist:
                    st.write(f"- {h[1]} — {h[2]}")
            else:
                st.info("구매 이력이 없습니다.")

        # 사이드바: 할일 추가 (로그인 시에만 보이게)
        st.sidebar.markdown("---")
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
                    safe_rerun()
                except Exception as e:
                    st.sidebar.error("할일 추가 중 오류: " + str(e))

        # 로그아웃
        if st.sidebar.button("로그아웃"):
            st.session_state.user = None
            safe_rerun()

    else:
        st.info("왼쪽 사이드바에서 로그인 또는 회원가입을 해주세요.")

# ---------- 안전 실행 래퍼 ----------
if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        st.title("앱 실행 중 오류가 발생했습니다.")
        st.error(str(e))
        st.text(traceback.format_exc())
        sys.exit(1)
