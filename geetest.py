import hmac
import json
import logging

import requests

with open("config.json", "r") as f:
    config = json.load(f)["geetest"]
enabled = config["enable"]
captcha_id = config["captcha_id"]
captcha_key = config["captcha_key"]
api_server = config["api_server"]


def verify_test(lot_number="", captcha_output="", pass_token="", gen_time=""):
    if not enabled:
        return {"result": "success", "reason": "Geetest is disabled."}
    # 生成签名
    # 生成签名使用标准的hmac算法，使用用户当前完成验证的流水号lot_number作为原始消息message，使用客户验证私钥作为key
    # 采用sha256散列算法将message和key进行单向散列生成最终的签名
    lotnumber_bytes = lot_number.encode()
    prikey_bytes = captcha_key.encode()
    sign_token = hmac.new(prikey_bytes, lotnumber_bytes, digestmod="SHA256").hexdigest()

    # 上传校验参数到极验二次验证接口, 校验用户验证状态
    query = {
        "lot_number": lot_number,
        "captcha_output": captcha_output,
        "pass_token": pass_token,
        "gen_time": gen_time,
        "sign_token": sign_token,
    }
    url = f"{api_server}/validate?captcha_id={captcha_id}"
    # 注意处理接口异常情况，当请求极验二次验证接口异常或响应状态非200时做出相应异常处理
    # 保证不会因为接口请求超时或服务未响应而阻碍业务流程
    try:
        res = requests.post(url, query)
        assert res.status_code == 200
        msg = res.json()
        if msg["result"] == "success":
            logging.info("Geetest captcha passed successfully.")
            return {"result": "success", "reason": msg["reason"]}
        else:
            return {"result": "fail", "reason": msg["reason"]}
    except Exception as e:
        return {
            "result": "error",
            "reason": "Failed to verify captcha. Please try again later.",
            "exception": e,
        }
