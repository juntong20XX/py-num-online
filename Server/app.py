#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用主体
注意由于nuc_ids线程不安全，请单线程运行
"""
# 第三方模块
from flask import Flask, request
import flask
# 内置模块
import os
import re
import io
import time
# 项目模块
import data
import nuc_ids

# 加载配置
data.load_config()

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    user_agent = request.headers.get('User-Agent')
    # 根据 HEADERS 判断连接是否为网站客户端
    # 校验user-agent正则表达式默认值为 r"^NumOnlineAPP/((\d+)\.(\d+)\.(\d+))$"
    if re.match(data.CONFIG_DATA["re_patterns"]["app_user_agent"], user_agent):
        # 是客户端, 将跳转到登录界面
        return flask.redirect(flask.url_for('app_login'))
    else:
        # 默认为浏览器端, 将跳转到管理界面
        return flask.redirect(flask.url_for('manager'))


@app.route("/manager", methods=['GET', 'POST'])
def manager():
    if request.method == "POST":
        # Post request
        if request.form.get("edit nuc save file"):
            # 修改NUC上的保存文件
            return manager_edit_nuc_save_file()
        elif request.form.get("SAVE TRACKED DATA"):
            # 保存跟踪中的数据集
            pass
    elif request.method == "GET":
        # Get request
        data.refresh_nuc()
        return flask.render_template("manager_base.html",
                                     trace_and_cache_data=data.track_and_cache_data,
                                     nucs=data.nuc)
    else:
        # not support
        return 'no support method "%s"' % request.method


def manager_save_track():
    """
    返回被更新的文件
    """
    nuc_id = request.form.get("save tracked data")
    for track_data in data.track_and_cache_data:
        if track_data["nuc"]["token"] == nuc_id:
            break
    else:
        return manager_error(error="找不到token对应的数据")
    data_string = data.track_to_string(data)
    steam = io.StringIO(data_string)
    return flask.send_file(steam, as_attachment=True)  # NOTE: 我觉得这段没问题......


def manager_error(**kwargs):
    """
    返回错误
    :return: str
    """
    return flask.render_template("error_base.html", **kwargs)


def manager_edit_nuc_save_file():
    """
    更新nuc端保存文件路径
    :return: str
    """
    # 获取新保存路径
    new_nuc_save_path = request.form.get("new nuc save file path")
    # 检查路径是否可用
    save_dir = os.path.dirname(new_nuc_save_path)
    if not os.path.isdir(save_dir):
        # 若该文件所在路径不存在, 检查其父路径是否存在
        d, d2 = os.path.split(save_dir)
        if not os.path.isdir(d):
            # 若该文件的父路径也不存在, 报错
            return manager_error(error="文件错误！不可创建多个文件")
        # 父路径存在, 新建文件夹
        try:
            os.mkdir(save_dir)
        except Exception as err:
            return manager_error(error=f"创建文件夹时出错 {err}")
        # 文件夹创建成功
    elif os.path.isfile(new_nuc_save_path):
        # 所选择文件已存在
        if not os.access(new_nuc_save_path, os.W_OK):
            # 没有写入权限, 报错
            return manager_error(error="没有写入权限")
    # 将路径写入配置
    data.CONFIG_DATA["paths_nuc"]["save_path"] = new_nuc_save_path
    data.save_config()
    # 返回新的文件名称
    data.refresh_nuc()
    return flask.render_template("manager_base.html",
                                 nuc_save_file_path=new_nuc_save_path,
                                 trace_and_cache_data=data.track_and_cache_data,
                                 nucs=data.nuc)


@app.route("/app_update", methods=['GET', 'POST'])
def app_update():
    """
    更新数据
    """
    if request.method == 'GET':
        return manager_error(error="please post the url")
    nuc_id = request.form.get("nuc_id")
    for nuc_data in data.nuc:
        if nuc_data["token"] == nuc_id:
            break
    else:
        return flask.jsonify(OK=False, error="未登录")
    value = {i: request.form[i] for i in request.form.keys()}
    if "data" in value:
        value["data"] = eval(value["data"])
    nuc_data.update(value)
    nuc_data["timestamp"] = time.time()
    return flask.jsonify(OK=True, id=nuc_id,
                         config=nuc_data.get("config_path", data.CONFIG_DATA["paths_nuc"]["config_path"]),
                         upload=nuc_data.get("upload_path", data.CONFIG_DATA["paths_nuc"]["upload_path"]))


@app.route("/app_upload_data", methods=['GET', 'POST'])
def app_upload_data():
    """
    接受上传的数据
    """
    if request.method == 'GET':
        return manager_error(error="please post the url")
    nuc_id = request.form.get("nuc_id")
    for nuc_data in data.nuc:
        if nuc_data["token"] == nuc_id:
            break
    else:
        return flask.jsonify(OK=False, error="未登录")
    nuc_data["timestamp"] = time.time()


@app.route("/app_login", methods=['GET', 'POST'])
def app_login():
    """
    客户端登录界面
    """
    data.refresh_nuc()
    if request.method == "POST":
        # Post request
        nuc_id = request.form.get("nuc_id")
        nuc_name = request.form.get("nuc_name")
        nuc_user = request.form.get("nuc_user")
        if not nuc_id:
            # 需要生成并返回id
            nuc_id = nuc_ids.generate_id(nuc_name, nuc_user)
            # 以 json 形式返回id
            return flask.jsonify({"id": nuc_id, "OK": False})
        # 尝试登录
        code = data.nuc_login(nuc_id, nuc_name, nuc_user)
        if code != 0:
            return flask.jsonify({"OK": False, "error-code": code})
        # 登录成功
        return flask.jsonify({"OK": True,
                              "id": nuc_id,
                              "config": data.CONFIG_DATA["paths_nuc"]["config_path"],
                              "upload": data.CONFIG_DATA["paths_nuc"]["upload_path"]})
    elif request.method == "GET":
        # Get request
        return flask.render_template("app_login.html")
    else:
        # not support
        return 'no support method "%s"' % request.method


@app.route("/manager/id=<nuc_id>", methods=["GET", "POST"])
def manager_id(nuc_id):
    if request.method == "GET":
        return manager_id_method_get(nuc_id)
    if request.form.get("save tracked data"):
        # 保存跟踪中的数据
        return manager_save_track()  # 两个页面api是一致的，可以放心调用
    elif request.form.get("track"):
        # 反转跟踪状态
        return manager_id_reversal_tracking_state(nuc_id)


def manager_id_method_get(nuc_id):
    for nuc in data.nuc:
        if nuc["token"] == nuc_id:
            break
    else:
        return manager_error(error="找不到id")
    is_tracking = "停止追踪" if nuc["token"] in data.get_nuc_info_from_track_and_cache_data() else "开始跟踪"
    return flask.render_template("manager_id.html",
                                 column=max(len(i) for i in nuc["data"]), nuc=nuc, is_tracking=is_tracking)


def manager_id_reversal_tracking_state(nuc_id):
    """
    供 manger_id 调用, 用于反转对某nuc的跟踪状态
    """
    # TODO: 添加or删除跟踪状态, 其实应该先写data的api
    return manager_id_method_get(nuc_id)  # 返回值和get方法返回内容一致


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001)
