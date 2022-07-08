#!/user/bin/env python
# -*- coding: utf-8 -*-
"""
客户端
警告: 默认配置中应用将扫描 192.168.*.* 共65536个IP网址, 且服务器IP可能没有在扫描列表中;
     默认扫描端口号为5001, 服务器可能应用与其他端口。 建议使用前先配置IP+端口
"""
import os
import re
import sys
import copy
import time
import typing
import threading
import itertools
import functools
import subprocess

import csv
import yaml
import requests

VERSION = "0.0.1"


class StopSettingIteration(Exception):
    pass


def get_user_name(default="False") -> str:
    if os.name == "win32":
        # Windows system
        return os.environ.get("USER" + "NAME", default)
    elif os.name == "posix":
        # Linux
        return os.environ.get("USER", default)
    else:
        # else
        try:
            return subprocess.getoutput("whoami")
        except OSError:
            # XXX: I'm not sure this exception.
            return default


def get_computer_name(default="False"):
    if os.name == "win32":
        # Windows system
        return os.environ.get("COMPUTER" + "NAME", default)
    elif os.name == "posix":
        # Linux
        return os.environ.get("NAME", default)
    else:
        # else
        try:
            return subprocess.getoutput("hostname")
        except OSError:
            # XXX: I'm not sure this exception.
            return default


def edit_dict_sort_key(value):
    value = str(value)
    try:
        i = ord(value[0])
    except IndexError:
        i = 0
    return 2 ** len(value) + i


def show_info(data: typing.Iterable, func: typing.Callable[[int, typing.Any], typing.Any]) -> None | re.Match:
    """
    在编辑函数中用于输出数据展示
    :param data: iterable
    :param func: 用于格式化输出, 接受两个参数，第一个为当前元素的序号（从1开始数）第二个是当前元素的内容
    :return:
    """
    for index, key in enumerate(data, 1):
        print(func(index, key))
    print()
    print("[a] : Add a new item")
    print("[r] : Remove an item")
    print("[q] : QUIT without save")
    print("[y] : SAVE")
    ans = input(">>> ")
    # 正则表达式匹配输入
    m = re.match(r"^(\d+)$|^([a|A](?:dd)?)$|^([r|R](?:emove)?)$|^(0|[qQ](?:uit)?)$|^([yY](?:es)?)$", ans)
    return m


def default_format_object_func(value_type, format_str) -> object:
    if value_type is None:
        return None
    elif value_type is Ellipsis:
        return None
    else:
        return value_type(format_str)


def input_an_item(value_type: None | type = None,
                  types: list | tuple = (str, int, float, bool, dict, list, None),
                  old_value: None | type = None,
                  format_func: typing.Callable[[type, str], object] = default_format_object_func) -> object:
    """
    获取编辑的变量值
    :param value_type:  返回对象的类型，若想返回 None, 请输入 Ellipsis
    :param types:       支持变化的类型
    :param old_value:   原先的值, 如果没有原先值, 输入 None; 若原先值是 None, 请输入 Ellipsis
    :param format_func: 实例化对象的函数
    :raise StopSettingIteration: 用户取消输入
    :return: 实例化的变量
    """
    # 获取对象类型
    while value_type is None:
        print("请选择想添加的类型:")
        for num, t in enumerate(types, 1):
            print(f"[{num}] : {t}")
        print()
        print("[q] : QUIT")
        ans = input(">>> ")
        if ans.isdecimal():
            ans = int(ans) - 1
            if ans >= len(types):
                print("无法识别输入")
            else:
                value_type = types[ans]
                if value_type is None:
                    return None
                print("input value ", end="" if old_value is None else "\n")  # 这段打印是为了优化体验
        elif ans in {"q", "Q", "quit", "Quit"}:
            raise StopSettingIteration("用户终止输入")
        else:
            print("识别失败")
    # 完成获取对象类型, 将获取新值
    if value_type is Ellipsis:
        return None
    if old_value is not None and not isinstance(old_value, value_type):
        # 旧值与新值类型不同
        old_value = None
    if value_type is list:
        backup = []
        ret = edit_list([] if old_value is None else copy.deepcopy(old_value), backup)
        if ret is backup:
            raise StopSettingIteration("用户终止输入")
        return ret
    if value_type is dict:
        backup = {}
        ret = edit_dict({} if old_value is None else copy.deepcopy(old_value), backup)
        if ret is backup:
            raise StopSettingIteration("用户终止输入")
        return ret
    while 1:
        if old_value is not None:
            print("╭ (\033[34m", None if old_value is Ellipsis else old_value, "\033[0m)")
            print("╰", end="")
        ans = input("─> ")
        try:
            return format_func(value_type, ans)
        except (ValueError, TypeError) as err:
            print("赋值时出错:", format(err))
            if old_value is None:  # 这段打印是为了优化体验
                print("input value ", end="")


def edit_list(data: list, backup: list) -> list:
    """
    返回修改后的数据，编辑时直接在 data 上修改, backup一定不被修改
    :param data:   将修改的数据
    :param backup: 数据的备份，可用是deepcopy(data)
    :return: new data
    """
    try:
        length = max(len(str(i)) for i in data)
    except ValueError:
        length = 0

    def format_func(index, value):
        return "[%d] : %s" % (index, str(value).center(length))

    while 1:
        m = show_info(data, format_func)
        if m is None:
            print("无法匹配")
            continue
        n, a, r, q, s = m.groups()
        if n:
            # 匹配到了数字
            key = int(n) - 1
            try:
                data[key] = input_an_item(type(data[key]), old_value=data[key])
            except StopSettingIteration:
                # 用户取消输入
                continue
            else:
                length = max(len(str(i)) for i in data)
        elif a:
            # 添加
            while 1:
                idx = input("new index (0~%d) >>> " % len(data))
                if idx.isdecimal():
                    idx = int(idx)
                    if idx > len(data):
                        print("数字过大")
                    else:
                        break
                elif idx == "":
                    print("默认插入末尾")
                    idx = len(data)
                    break
                else:
                    print("无法匹配")
            print("请输入要添加的值:")
            try:
                v = input_an_item()
            except StopSettingIteration:
                print("用户取消输入")
            else:
                # 添加值
                data.insert(idx, v)
                # 更新显示配置
                length = max(len(str(i)) for i in data)
        elif r:
            # 删除
            if len(data) == 0:
                print("No item to remove.")
                continue
            idx = input("input number for remove >>>")
            if idx.isdecimal():
                idx = int(idx) - 1
                if idx >= len(data):
                    print("数字过大")
                else:
                    # 删除
                    data.pop(idx)
                    # 更新显示配置
                    length = max(len(str(i)) for i in data)
            else:
                print("Cancel...")
        elif q:
            # 退出, 直接返回备份
            return backup
        else:  # Save
            return data


def edit_dict(data: dict, backup: dict) -> dict:
    """
    返回修改后的数据，编辑时直接在 data 上修改, backup一定不被修改
    :param data:   将修改的数据
    :param backup: 数据的备份，可用是deepcopy(data)
    :return: new data
    """
    keys = sorted(data.keys(), key=edit_dict_sort_key)
    try:
        length = max(len(str(i)) for i in data.keys())
    except ValueError:
        length = 0

    def format_func(num, k):
        return "[%d] : %s : %s" % (num, str(k).center(length), data[k])

    while 1:
        m = show_info(keys, format_func)
        if m is None:
            print("无法匹配")
            continue
        n, a, r, q, s = m.groups()
        # 获取修改内容
        if n:
            # 匹配到了数字
            key = keys[int(n) - 1]
            if isinstance(data[key], (str, int, float, bool)) or data[key] is None:
                while 1:
                    print("╭ (\033[34m", data[key], "\033[0m) <-", key)
                    print("╰", end="")
                    try:
                        data[key] = input_an_item(None if data[key] is None else type(data[key]))
                    except StopSettingIteration:
                        # 用户取消输入
                        break
                    else:
                        break
            elif isinstance(data[key], dict):
                data[key] = edit_dict(data[key], copy.deepcopy(backup[key]))
            elif isinstance(data[key], list):
                data[key] = edit_list(data[key], copy.deepcopy(backup[key]))
            else:
                print("不支持此类型配置")
        elif a:
            # 添加值
            new_key = Ellipsis  # 由于 input_an_item 不能生成Ellipsis, 可以 Ellipsis 为关键字
            new_value = Ellipsis
            while new_key is Ellipsis:
                print("请输入键:")
                try:
                    new_key = input_an_item(types=(str, int, float, bool, None))
                except StopSettingIteration:
                    # 用户取消输入
                    break
                if new_key in data:
                    print("该键已存在")
            if new_key is Ellipsis:
                # 取消输入
                continue
            while new_value is Ellipsis:
                print("请输入值:")
                try:
                    new_value = input_an_item()
                except StopSettingIteration:
                    # 用户取消输入
                    break
            if new_value is Ellipsis:
                # 取消输入
                continue
            # 输入完毕, 赋值
            data[new_key] = new_value
            # 刷新显示数据
            keys = sorted(data.keys(), key=edit_dict_sort_key)
            try:
                length = max(len(str(i)) for i in data.keys())
            except ValueError:
                length = 0
        elif r:
            # 删除元素
            while 1:
                for index, key in enumerate(keys, 1):
                    print("[%d]" % index, ":", str(key).center(length))
                print()
                print("[C] : cancel")
                ans = input(">>> ")
                if ans.isdecimal():
                    # 输入了数字
                    ans = int(ans) - 1
                    if ans >= len(keys):
                        print("数字 %d 过大, 请检查输入" % ans)
                    else:
                        # 删除
                        data.pop(keys[ans])
                        # 刷新显示数据
                        keys = sorted(data.keys(), key=edit_dict_sort_key)
                        length = max(len(str(i)) for i in data.keys())
                        # 删除后跳出循环
                        break
                elif ans in {"q", "Q", "quit", "Quit", "c", "C", "Cancel", "cancel", ""}:
                    # 取消删除
                    break
                else:
                    print("无法识别, 请检查输入")
        elif q:
            return backup
        else:  # save
            return data


def generate_config() -> dict:
    """
    生成配置
    """
    config = {'config_file': '~/.pyNumOnline/config.yaml',
              'upload_file': '~/.pyNumOnline/upload.csv',
              'search': {'ips': ["192.168.*.*"], 'timeout': 1, "threads": 10},
              'upload': {'signal_port': 5432, 'command_text': 'send_file'},
              'server': {'server_port': 5001, 'upload_delay(s)': 500, 'reconnect_times': 40, 'ping_delay(s)': 15}}
    backup = copy.deepcopy(config)
    ans = None
    print(">>> 开始设置 <<<")
    while ans is None:
        ans = input("使用默认配置吗？[Y|n]")
        if ans.lower() in {"yes", "y", ""}:
            ans = 1
        elif ans.lower() in {"n", "no"}:
            ans = 0
    if ans == 1:
        # 使用默认配置, 直接返回即可
        return config
    # 开始手动配置
    new_config = edit_dict(config, backup)
    if new_config is backup:
        raise StopSettingIteration("手动退出")
    else:
        return new_config


def read_config_from(path: str):
    with open(os.path.expanduser(path), "r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp)
    return config


def write_config_to(path: str, data):
    path = os.path.expanduser(path)
    config = data
    if os.path.isfile(path):
        config = None
        try:
            with open(path, "r", encoding="utf-8") as fp:
                config = yaml.safe_load(fp)
        finally:
            if not isinstance(config, dict):
                config = data
            else:
                config.update(data)
    with open(path, "w") as fp:
        yaml.safe_dump(config, fp)


def init():
    """
    初始化
    """
    config_dir = os.path.expanduser("~/.pyNumOnline")
    if os.path.isdir(config_dir):
        # 存在配置文件夹
        ls = os.listdir(config_dir)
        if "config.yaml" in ls:
            # 存在配置文件
            try:
                with open(os.path.expanduser("~/.pyNumOnline/config.yaml"), "r", encoding="utf-8") as fp:
                    config = yaml.safe_load(fp)
            except Exception as err:
                # 配置加载失败
                print(f"配置加载失败: {err}")
            else:
                # 返回配置
                return read_config_from(config["config_file"])
    else:
        # 没有配置文件夹, 创建
        os.mkdir(os.path.expanduser("~/.pyNumOnline"))
    # 没有找到配置文件, 开始输入配置
    try:
        config = generate_config()
    except StopSettingIteration as err:
        print("已停止配置")
        raise err
    # 生成结束, 写入配置
    write_config_to("~/.pyNumOnline/config.yaml", config)
    # 返回配置
    return read_config_from(config["config_file"])


def ping_function(ip, port, timeout) -> bool:
    """
    用于尝试输入的IP:port是否为NumOnline服务器
    :param ip:      将尝试的IP或网址
    :param port:    端口
    :param timeout: 最大时间
    :return: 该IP是否连接成功
    """
    url = f"http://{ip}:{port}"
    # print(url, end="", flush=True)
    try:
        r = requests.get(url, headers={"User-Agent": f"NumOnlineAPP/{VERSION}"}, timeout=timeout)
        r.raise_for_status()
    except (requests.exceptions.InvalidSchema, requests.exceptions.ConnectionError):
        return False
    return r.url.endswith("/app_login")


def ping_thread_target(ls, ips, port, timeout):
    for ip in ips:
        ls.append(ping_function(ip, port, timeout))


def try_ips(ips: typing.Iterable[str], port: int, timeout: int = 1, threads: int = 1) -> list[str]:
    """
    多线程尝试ips中的地址是否是服务器IP
    :return: 可用的IP
    """
    ips = list(ips)
    groups = []
    ip_ok = []
    pool = []
    for i in range(threads):
        ok = []
        ip_ok.append(ok)
        group = ips[i::threads]
        groups.append(group)
        t = threading.Thread(target=functools.partial(ping_thread_target, ok, group, port, timeout), daemon=True)
        pool.append(t)
        t.start()
    number = len(ips)
    times = -1
    texts = ("—", "\\", "|", "/")
    dl = len(str(number))
    while any(t.is_alive() for t in pool):
        times = (times + 1) % 4
        s = sum(len(i) for i in ip_ok)
        percentage = s / number * 100
        text = f"scanning... [%{dl}d/%{dl}d | %3.1f%%] %s"
        print("\r" + text % (s, number, percentage, texts[times]), end="", flush=True)
        time.sleep(0.3)
    print()

    ip_ok = itertools.chain.from_iterable(ip_ok)
    return list(itertools.compress(itertools.chain.from_iterable(groups), ip_ok))


def ip_config_part_to_real(ip_config_part: str) -> list[int]:
    if ip_config_part.isdecimal():
        ip_config_part = int(ip_config_part)
        if ip_config_part > 255:
            raise ValueError("IP %s 数字过大" % ip_config_part)
        return [ip_config_part]
    m = re.match(r"^\{(\d+), ?(\d+)}$", ip_config_part)
    if m:
        sta, end = m.groups()
        return [i for i in range(int(sta), int(end) + 1)]
    if ip_config_part == "*":
        return [i for i in range(256)]
    raise ValueError("IP 未能识别, %s" % ip_config_part)


def ip_config_to_ip_list(ip_config: str) -> list[str]:
    """
    将ip配置文本转为真实IP
    ip_config: 192.168.1.1 表示单个IP;
               192.168.1.* 表示遍历 192.168.1.1 ~ 192.168.1.255;
               192.168.1.{1,3} 表示遍历 192.168.1.1 ~ 192.168.1.3
    :param ip_config: ip配置文本
    :return: iterable
    """
    values = ip_config.split(".")
    if len(values) != 4:
        raise ValueError("IP识别错误")
    a, b, c, d = (ip_config_part_to_real(i) for i in values)
    return [f"{ip_1}.{ip_2}.{ip_3}.{ip_4}" for ip_1 in a for ip_2 in b for ip_3 in c for ip_4 in d]


def scan_and_choose_url(ip_config, port, timeout, threads):
    ips = list(itertools.chain.from_iterable(ip_config_to_ip_list(i) for i in ip_config))
    ip_ok = try_ips(ips, port, timeout, threads)
    # 扫描结束
    if not ip_ok:
        raise ValueError("找不到服务器")
    if len(ip_ok) > 1:
        print("找到了多个服务器, 请选择登录哪一个:")
        while 1:
            for i, ip in ip_ok:
                print("[%d] : %s:%d" % (i, ip, port))
            i = input("\n>>> ")
            if i.isdecimal():
                i = int(i)
                if i > len(ip_ok):
                    print("数字错误")
                else:
                    return ip_ok[i]
            else:
                print("无法识别")
    else:
        # 只扫描到了一个网址
        return ip_ok[0]


def login(url: str, my_id: str | None) -> dict:
    r = requests.post(url, headers={"User-Agent": f"NumOnlineAPP/{VERSION}"},
                      data={"nuc_name": get_computer_name(),
                            "nuc_user": get_user_name(),
                            "nuc_id": my_id})
    r.raise_for_status()
    j = r.json()
    if j["OK"]:
        return j
    else:
        if my_id is None:
            return login(url, j["id"])  # XXX : 不会收集错误
        else:
            raise Exception("服务器登录失败，错误代码", j["error-code"])


def update_to_server(url, timeout=1, ping_times=3, ping_delay=1000, data=None, **kwargs):
    if data:
        kwargs.update(data)
    for _ in range(ping_times):
        try:
            r = requests.post(url, headers={"User-Agent": f"NumOnlineAPP/{VERSION}"},
                              data=kwargs,
                              timeout=timeout)
            r.raise_for_status()
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as err:
            print(type(err).__name__, err)
            time.sleep(ping_delay)
        else:
            break
    else:
        raise TimeoutError("连接服务器失败, 达到最大重连次数")
    return r.json()


def main(config_file: str, search: dict, upload_file: str, server: dict, **kwargs):
    """
    输入写在配置文件中
    :param config_file:
    :param search:
    :param upload_file:
    :param server:
    """
    argv = sys.argv[1:]
    # 获取服务器地址
    port = server["server_port"]
    timeout = search["timeout"]
    if argv:
        # 服务器地址已输入
        ip = argv[0]
        if ":" in ip:
            ip, port = ip.split(":")
            port = int(port)
        assert ping_function(ip, port, timeout), ValueError("输入的IP未识别为服务器")
    else:
        # 扫描并获得服务器地址
        last_ip = kwargs.get("last_ip")
        if last_ip and ping_function(last_ip, port, timeout):
            ip = last_ip
        else:
            ip = scan_and_choose_url(search["ips"], port, timeout, search["threads"])
    url_base = f"http://{ip}:{port}"

    ping_times = server["reconnect_times"]
    ping_delay = server["ping_delay(s)"]
    my_id = kwargs.get("id")
    # 登录完成, 获得了服务器端配置
    config = login(url_base + "/app_login", my_id)
    write_config_to(config_file, {"id": config["id"], "last_ip": ip})
    start = time.time()
    times = -1
    while 1:  # 工作循环
        run_continue = False
        # 检查配置
        my_id = config["id"]
        if os.path.expanduser(config["config"]) != os.path.expanduser(config_file):
            config_file = config["config"]
            write_config_to(config_file, {"id": config["id"], "last_ip": ip})
            write_config_to("~/.pyNumOnline/config.yaml", {"config_file": config_file})
        _upload = config["upload"]
        if _upload is not None:
            if os.path.expanduser(_upload) != os.path.expanduser(upload_file):
                upload_file = _upload
                write_config_to(config_file, {"upload_file": upload_file})
        else:
            # 要告知服务器本机上传文件
            for _ in range(timeout):
                config = update_to_server(url_base + "/app_update", timeout, ping_times,
                                          upload_file=upload_file, nuc_id=my_id)
                if not config["OK"]:
                    print("配置更新失败 :", config["error"])
                    if config["error"] == "未登录":
                        config = login(url_base + "/app_login", my_id)
                        run_continue = True
                        break
                    # 其余错误只好重试
                else:
                    break
            else:
                raise TimeoutError("配置上传失败")
        if run_continue:
            continue
        if time.time() - start > server["upload_delay(s)"] / 1000:
            print("上传数据 ...", end="", flush=True)
            try:
                with open(os.path.expanduser(upload_file), "r", encoding="utf-8") as fp:
                    r = csv.reader(fp)
                    data = list(r)
            except FileNotFoundError:
                # 找不到文件
                print("上传文件未找到")
                continue
            for _ in range(timeout):
                config = update_to_server(url_base + "/app_update", timeout, ping_times, ping_delay,
                                          {"data": format(data), "nuc_id": my_id})
                if not config["OK"]:
                    print("  配置更新失败 : %s" % config["error"], end="", flush=True)
                    if config["error"] == "未登录":
                        config = login(url_base + "/app_login", my_id)
                        break
                    # 其余错误只好重试
                else:  # 刷新时间
                    times = (times + 1) % 6
                    print("\r%s上传成功 !" % ("." * times).ljust(5), end="", flush=True)
                    start = time.time()
                    break
            else:
                raise TimeoutError("配置上传失败")


if __name__ == "__main__":
    # Initiation
    cfg = init()
    try:
        main(**cfg)
    except (KeyError, ValueError) as e:
        print("配置错误", e)
        bp = copy.deepcopy(cfg)
        new = edit_dict(cfg, bp)
        if new is bp:
            raise StopSettingIteration("手动退出")
        else:
            write_config_to("~/.pyNumOnline/config.yaml", cfg)
            main(**cfg)
