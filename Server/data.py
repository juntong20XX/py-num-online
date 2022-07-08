#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理
"""
import os
import re
import time
import typing
import collections

import yaml

CONFIG_PATH = os.path.dirname(__file__).replace("\\", "/") + "/" + "config.yaml"

CONFIG_DATA = {
    "re_patterns": {
        "app_user_agent": r"^NumOnlineAPP/((\d+)\.(\d+)\.(\d+))$",
        "nuc_user_name": r".*",  # 登陆端用户名称规范
        "nuc_computer_name": r".*",  # 登陆端计算机名称规范
    },
    "paths_nuc": {  # nuc 端的路径配置
        "upload_path": None,
        "config_path": "~/.pyNumOnline/config.yaml",
    },
    "paths_server": {  # 服务器端配置
        # "track_to": "~/.pyNumOnline/{nuc_name}/track.csv",  # 服务器端保存数据位置
    },
    "connection": {  # 连接设置
        "nuc_app_cookie": {
            "User-Agent": "NumOnlineAPP/{VERSION}",
        },
        "nuc_disconnect_time(s)": 4,  # 若超过此时间nuc未更新数据，则断开连接
    }
}

# 已连接的 nuc
# 元素格式:
# {
#     "name": "test",
#     "token": "123",
#     "last": 3.1,
#     "user": "abc",
#     "timestamp": time.time(),
#     "upload_file": "~/.pyNumOnline/upload.txt",
#     "data": [],  # CSV list
# }
nuc = [
]

# 跟踪并缓存的数据
# 元素格式:
# {
#    "nuc": {...},  # 此数据nuc信息, 就是nuc列表的元素
#    "data": {time_1: {...}, time_2: {...}},  # 数据情况，单位是ns
#    "last_update": {...}  # 上次更新的时间
# }
track_and_cache_data = []


def get_real_path(path: str):
    """
    处理home路径问题, 将路径分隔符由"\"无脑转为为"/"
    :param path: path-like string
    :return: str
    """
    path = os.path.expanduser(path)
    return path.replace("\\", "/")


def load_config(config_path=None, encoding="utf-8"):
    """
    加载配置到app.CONFIG_DATA
    :param config_path: path-like str, or None, None will use app.CONFIG_PATH
    :param encoding: str, the value for function `open`
    :return: new
    """
    if config_path is None:
        config_path = CONFIG_PATH
    with open(config_path, "r", encoding=encoding) as fp:
        new = yaml.safe_load(fp)
    if isinstance(new, dict):
        CONFIG_DATA.update(new)
    return new


def save_config(config_path=None):
    """
    将app.CONFIG_DATA写入路径
    :param config_path: path-like str, or None, None will use app.CONFIG_PATH
    :return: None
    """
    if config_path is None:
        config_path = CONFIG_PATH
    with open(config_path, "w") as fp:
        yaml.safe_dump(CONFIG_DATA, fp)


def nuc_id_list() -> list[str, ...]:
    """
    获取所有登录端的令牌
    :return: 所有令牌
    """
    return [i["token"] for i in nuc]


def nuc_check_token(token) -> int:
    """
    检查一个令牌是否可用
    :param token: 带检查的令牌
    :return: 0: 令牌合理, 1: 令牌已存在, 2: 令牌长度不合理
    """
    if len(token) != 32:
        # 令牌长度不合理
        return 2
    if token in nuc_id_list():
        # 令牌已存在
        return 1
    # 令牌合理
    return 0


def refresh_nuc():
    """
    更新nuc的时间数据。如果超过时间则删除连接。
    """
    timestamp = time.time()
    index_for_remove = []
    for i, n in enumerate(nuc):
        last = timestamp - n["timestamp"]
        n["last"] = round(last, 1)
        if last > CONFIG_DATA["connection"]["nuc_disconnect_time(s)"]:
            # 先将要删除的下标存入, 避免边迭代边修改
            index_for_remove.append(i - len(index_for_remove))  # 减去 len(index_for_remove) 是为了适配已经删去部分值的nuc列表
    while index_for_remove:
        nuc.pop(index_for_remove.pop(0))


def get_nuc_info_from_track_and_cache_data():
    """
    :return: 被跟踪且缓存的列表中的nuc数据
    """
    for data in track_and_cache_data:
        nuc_data = data["nuc"]
        if nuc_data in nuc:
            yield nuc_data


def nuc_login(nuc_id, nuc_name, nuc_user) -> int:
    """
    添加登录
    :param nuc_id: str 令牌
    :param nuc_name: str 主机名称
    :param nuc_user: str 用户名称
    :return: 0->一切正常, 1~10->nuc_check_token出错, 11->计算机名称出错, 12->用户名出错
    """
    # 检查计算机名称是否合规
    if not re.match(CONFIG_DATA["re_patterns"]["nuc_computer_name"], nuc_name):
        return 11
    # 检查用户名是否合规
    if not re.match(CONFIG_DATA["re_patterns"]["nuc_user_name"], nuc_user):
        return 12
    # 最后检查一个令牌是否可用
    code = nuc_check_token(nuc_id)
    if code != 0:
        return code
    for nuc_data in get_nuc_info_from_track_and_cache_data():
        if nuc_data["name"] == nuc_name and nuc_data["user"] == nuc_user:
            # 发现正在登陆的nuc在缓存中
            nuc_data["timestamp"] = time.time()  # 更新时间戳
            nuc.append(nuc_data)
            break
    else:
        # 建立并添加新的登录信息
        nuc.append({"token": nuc_id, "user": nuc_user, "name": nuc_name, "last": 0, "timestamp": time.time()})
    return 0


def track_to_string(track_data: dict[int: typing.Iterable[list]]) -> str:
    """
    将追踪并缓存的数据转换为yaml文本
    """
    data = collections.OrderedDict()  # XXX: 好像现在普通的字典也有序了？
    for key in sorted(track_data):
        data[key] = track_data[key]
    return yaml.safe_dump_all(data)
