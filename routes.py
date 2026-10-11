import uuid
from flask import render_template, request, redirect, url_for, session
import math
import random
from . import seats_bp

# ========== 工具函数 ==========

def parse_id_list(text):
    """
    将诸如 "1-20,45,47" 解析成 [1..20,45,47].
    可做更严格的异常处理, 这里只是示例.
    """
    result = set()
    parts = text.split(",")
    for p in parts:
        p = p.strip()
        if "-" in p:
            # range
            left, right = p.split("-",1)
            try:
                start = int(left)
                end   = int(right)
                if start<=end:
                    for x in range(start,end+1):
                        result.add(x)
            except:
                pass
        else:
            # single number
            try:
                val = int(p)
                result.add(val)
            except:
                pass
    return sorted(result)

def build_students(male_ids, female_ids):
    """
    根据用户输入的male_ids, female_ids -> [{id, gender}...]
    """
    students = []
    for mid in male_ids:
        students.append({'id': mid, 'gender': '男'})
    for fid in female_ids:
        students.append({'id': fid, 'gender': '女'})
    # 不做额外去重,假设用户输入没冲突
    return students

def push_empty_to_last(seats):
    rows = len(seats)
    if rows==0:
        return
    cols = len(seats[0])
    all_stu = []
    for r in range(rows):
        for c in range(cols):
            if seats[r][c] is not None:
                all_stu.append(seats[r][c])
    # 清空
    for r in range(rows):
        for c in range(cols):
            seats[r][c] = None
    idx=0
    for r in range(rows):
        for c in range(cols):
            if idx<len(all_stu):
                seats[r][c] = all_stu[idx]
                idx+=1
            else:
                break

# ========== 核心排座(简化与之前类似) ==========

def seat_assign(rows, cols, students, allow_mix, special_needs, must_share, must_diff):
    # 0) 先看是否需要增排
    total_stu = len(students)
    seat_capacity = rows*cols
    if seat_capacity < total_stu:
        rows = math.ceil(total_stu / cols)

    # 初始化 seats
    seats= [[None for _ in range(cols)] for _ in range(rows)]
    assigned_ids= set()

    # A) 放特殊需求
    sid_map = { s['id']: s for s in students }
    for sid,(rr,cc) in special_needs.items():
        if sid in sid_map and 0<=rr<rows and 0<=cc<cols and seats[rr][cc] is None:
            seats[rr][cc]= sid_map[sid]
            assigned_ids.add(sid)

    # B) 必须同桌
    #   这里先把座位按"每桌=2个位置"拆成 group_info
    group_info = []
    for r in range(rows):
        # 一行可能有若干个桌子(每桌2个seat)
        for gi in range(cols//2):
            cstart= gi*2
            p1= seats[r][cstart]
            p2= seats[r][cstart+1]
            group_info.append([p1,p2])

    must_not_share_ids = set(x for pair in must_diff for x in pair)
    s_map = { s['id']: s for s in students }

    g_idx=0
    for (s1, s2) in must_share:
        if s1 not in s_map or s2 not in s_map:
            continue
        if s1 in assigned_ids and s2 in assigned_ids:
            continue
        found= False
        while g_idx< len(group_info):
            desk = group_info[g_idx]
            if desk[0] is None and desk[1] is None:
                desk[0] = s_map[s1]
                desk[1] = s_map[s2]
                assigned_ids.update([s1,s2])
                found=True
                g_idx+=1
                break
            g_idx+=1

    # C) 填剩余
    leftover= [s for s in students if s['id'] not in assigned_ids]
    random.shuffle(leftover)

    for desk in group_info:
        s1,s2 = desk
        if s1 and s2:
            continue  # 这一桌已坐满
        elif s1 and not s2:
            occ_gender= s1['gender']
            candi=None
            for x in leftover:
                if allow_mix or x['gender']==occ_gender:
                    candi= x
                    break
            if candi:
                desk[1]= candi
                leftover.remove(candi)
                assigned_ids.add(candi['id'])
        elif s2 and not s1:
            occ_gender= s2['gender']
            candi= None
            for x in leftover:
                if allow_mix or x['gender']==occ_gender:
                    candi= x
                    break
            if candi:
                desk[0]= candi
                leftover.remove(candi)
                assigned_ids.add(candi['id'])
        else:
            # desk空
            if len(leftover)==0:
                break
            p1= leftover.pop()
            desk[0]= p1
            assigned_ids.add(p1['id'])
            if len(leftover)>0:
                if allow_mix:
                    p2= leftover.pop()
                    desk[1]= p2
                    assigned_ids.add(p2['id'])
                else:
                    occ_gender= p1['gender']
                    idx2=-1
                    for i,xx in enumerate(leftover):
                        if xx['gender']==occ_gender:
                            idx2= i
                            break
                    if idx2>=0:
                        p2= leftover.pop(idx2)
                        desk[1]= p2
                        assigned_ids.add(p2['id'])

    # 将 group_info 写回 seats
    idx=0
    for r in range(rows):
        for gi in range(cols//2):
            cstart= gi*2
            p1, p2= group_info[idx]
            seats[r][cstart]= p1
            seats[r][cstart+1]= p2
            idx+=1

    # 将最后空位"推到最后"
    push_empty_to_last(seats)

    # ========== 在此处为每个已分配的 seat 加上标识字段 ==========

    # 1) 根据 special_needs 构造一个set, 只要学号在里边就 is_special=True
    special_ids = set(special_needs.keys())
    
    # 2) 对于"必须同桌"与"不能同桌"的学号, 只要学号在对应pairs里即可标 True
    must_share_ids = set()
    for x,y in must_share:
        must_share_ids.add(x)
        must_share_ids.add(y)

    must_diff_ids = set()
    for x,y in must_diff:
        must_diff_ids.add(x)
        must_diff_ids.add(y)

    # 3) 遍历 seats, 给每个 seat(字典) 补充 3 个布尔字段
    for r in range(rows):
        for c in range(cols):
            seat = seats[r][c]
            if seat is not None:
                seat_id = seat["id"]
                seat["is_special"]    = (seat_id in special_ids)
                seat["is_must_share"] = (seat_id in must_share_ids)
                seat["is_must_diff"]  = (seat_id in must_diff_ids)

    return seats

# ========== Flask 路由 ==========

@seats_bp.route("/")
def home():
    # 清除可能的旧session，确保用户重新登录
    session.clear()
    return redirect(url_for("seats.login_page"))

@seats_bp.route("/login", methods=["GET","POST"])
def login_page():
    if request.method=="POST":
        male_ids_str = request.form.get("male_ids","").strip()
        female_ids_str = request.form.get("female_ids","").strip()

        # 解析
        male_list   = parse_id_list(male_ids_str)
        female_list = parse_id_list(female_ids_str)

        if len(male_list)==0 and len(female_list)==0:
            return render_template("seats_login.html", warning_msg="男生或女生学号至少要有一个")

        # 清除旧session，设置新的用户数据
        session.clear()
        session["user_id"] = str(uuid.uuid4())
        session["male_ids"] = male_list
        session["female_ids"] = female_list
        
        return redirect(url_for("seats.main_page"))
    else:
        # GET请求时也清除session，确保干净的开始
        session.clear()
        return render_template("seats_login.html")

@seats_bp.route("/main", methods=["GET"])
def main_page():
    # 若没登录,回login
    if "user_id" not in session or "male_ids" not in session or "female_ids" not in session:
        return redirect(url_for("seats.login_page"))
    
    user_id = session["user_id"]
    male_ids = session["male_ids"]
    female_ids = session["female_ids"]
    
    return render_template("seats_index.html",
        user_id=user_id,
        male_count=len(male_ids),
        female_count=len(female_ids),
        seats=None,
        rows=0,
        cols=0,
        warning_msg=""
    )

@seats_bp.route("/seat_result", methods=["POST"])
def seat_result():
    if "user_id" not in session or "male_ids" not in session or "female_ids" not in session:
        return redirect(url_for("seats.login_page"))
    
    user_id = session["user_id"]
    male_ids = session["male_ids"]
    female_ids = session["female_ids"]

    # 1) 读取表单
    try:
        cols= int(request.form.get("cols","8").strip())
        rows= int(request.form.get("rows","5").strip())
    except ValueError:
        return render_template("seats_index.html",
            user_id=user_id,
            male_count=len(male_ids),
            female_count=len(female_ids),
            seats=None, rows=0, cols=0,
            warning_msg="排数/列数应是整数"
        )

    allow_mix = (request.form.get("allow_mix")=="yes")

    special_text= request.form.get("special_needs","0").strip()
    must_share_text= request.form.get("must_share","0").strip()
    must_diff_text = request.form.get("must_diff","0").strip()

    # 2) 构建学生
    students= []
    for mid in male_ids:
        students.append({"id": mid, "gender":"男"})
    for fid in female_ids:
        students.append({"id": fid, "gender":"女"})

    # 3) 解析(仅做简单示例解析)
    def parse_constraints(text):
        arr=[]
        if text and text!="0":
            segs= text.split(";")
            for s in segs:
                s= s.strip()
                if "," in s:
                    left,right = s.split(",",1)
                    try:
                        sid1= int(left)
                        sid2= int(right)
                        arr.append((sid1,sid2))
                    except:
                        pass
        return arr

    # 解析"指定学号坐在第几排第几列"
    special_needs= {}
    if special_text and special_text!="0":
        segs= special_text.split(";")
        for s in segs:
            s= s.strip()
            if "=" in s:
                left, right= s.split("=",1)
                sid_str= left.strip()
                coord_str= right.strip().strip("()")
                if "," in coord_str:
                    r_str,c_str= coord_str.split(",",1)
                    try:
                        sid= int(sid_str)
                        rr= int(r_str.strip())-1  # 减1,转换成索引
                        cc= int(c_str.strip())-1
                        special_needs[sid]= (rr,cc)
                    except:
                        pass

    must_share= parse_constraints(must_share_text)
    must_diff = parse_constraints(must_diff_text)

    # 4) 分配
    seats= seat_assign(
        rows=rows, cols=cols,
        students=students,
        allow_mix=allow_mix,
        special_needs=special_needs,
        must_share=must_share,
        must_diff=must_diff
    )

    # 5) 将 seats 传给模板渲染
    return render_template("seats_index.html",
        user_id=user_id,
        male_count=len(male_ids),
        female_count=len(female_ids),
        seats=seats,
        rows=len(seats),
        cols=len(seats[0]) if len(seats)>0 else 0,
        warning_msg=""
    )