import json
import os
import sys
from openai import OpenAI


def load_prompts(file_path="config/prompts.txt"):
    """解析自定义文本格式的 Prompt 配置文件"""
    prompts = {}
    current_key = None
    current_content = []

    if not os.path.exists(file_path):
        print(f"[-] 错误: 找不到 Prompt 配置文件 {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if current_key:
                    prompts[current_key] = (
                        "\n".join(current_content).strip()
                    )
                current_key = stripped[1:-1]
                current_content = []
            else:
                if current_key is not None:
                    current_content.append(line.rstrip())

        if current_key:
            prompts[current_key] = "\n".join(current_content).strip()

    return prompts


def init_api_client(channel_config):
    """根据路由配置动态初始化对应的模型客户端"""
    api_key = os.environ.get(channel_config["api_key_env"])
    if not api_key:
        print(
            f"[-] 错误: 未检测到环境变量 {channel_config['api_key_env']}"
        )
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url=channel_config["base_url"])
    return client, channel_config["model_name"]


def ask_agent(client, model, system_prompt, user_content, temperature):
    """单次调用，维持无污染的上下文隔离"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[-] API 通道异常 ({model}): {e}")
        sys.exit(1)


def main():
    # 1. 加载配置与解析纯文本 Prompt
    with open("config/api_settings.json", "r", encoding="utf-8") as f:
        api_settings = json.load(f)
    prompts = load_prompts()

    routing = api_settings["runtime_routing"]
    channels = api_settings["channels"]

    # 2. 动态路由分发：初始化架构师与评审员的 API 客户端
    print(
        f"[*] 正在初始化模型路由... \n    [架构师]: {routing['architect_channel']} \n    [评审员]: {routing['reviewer_channel']}"
    )
    arch_client, arch_model = init_api_client(
        channels[routing["architect_channel"]]
    )
    rev_client, rev_model = init_api_client(
        channels[routing["reviewer_channel"]]
    )

    # 业务输入
    requirement = "设计一个支持高并发、低延迟的分布式数据缓存同步方案，需解决缓存击穿、双写一致性问题，并给出核心数据结构设计。"

    print("[*] 正在启动多智能体博弈系统...")
    print(f"[1/3] 正在调用【{arch_model}】构建初始技术方案...")
    current_doc = ask_agent(
        arch_client,
        arch_model,
        prompts["architect_system"],
        f"原始需求：{requirement}",
        routing["temperature"],
    )

    max_rounds = routing["max_rounds"]
    for r in range(1, max_rounds + 1):
        print(
            f"[2/3] 进入第 {r} 轮交叉验证：正在调用【{rev_model}】进行独立盲审..."
        )
        feedback = ask_agent(
            rev_client,
            rev_model,
            prompts["reviewer_system"],
            f"请盲审以下技术文档，直接指出其中的漏洞与不合理之处：\n\n{current_doc}",
            routing["temperature"],
        )

        print(
            f"[3/3] 第 {r} 轮审计意见已返回，正在交由【{arch_model}】进行文档修复..."
        )
        architect_input = (
            f"这是你前一版的设计文档：\n\n{current_doc}\n\n"
            f"这是外部独立审计专家给出的修改意见：\n\n{feedback}\n\n"
            f"请结合上述意见，输出优化后的全新一版技术设计文档。"
        )
        current_doc = ask_agent(
            arch_client,
            arch_model,
            prompts["architect_system"],
            architect_input,
            routing["temperature"],
        )

    os.makedirs("outputs", exist_ok=True)
    output_path = "outputs/DESIGN_DOCUMENT.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(current_doc)

    print(f"[+] 交叉验证迭代结束。高可信度文档已输出至: {output_path}")


if __name__ == "__main__":
    main()