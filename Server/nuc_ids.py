#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
被管理端 ID 管理模块
"""

import time
import hashlib


def generate_id(nuc_name, nuc_user) -> str:
    """
    生成一个nuc_id, nuc_id会是md5(注册时间+主机名称+登录用户名)
    :param nuc_name: nuc 主机名
    :param nuc_user: nuc 用户名
    WARING: 不检查输入是否正确, 不检查冲突
    :return:
    """
    text = str(time.time_ns()) + str(nuc_name) + str(nuc_user)
    return hashlib.md5(text.encode()).hexdigest()
