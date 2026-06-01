"""cv-review 命令行入口模块。

提供全局可用的 ``cv-review`` CLI，支持以下子命令与参数：
- ``cv-review init``：初始化用户级配置目录 ``~/.cv-review/``。
- ``cv-review --file <path> [--instruction "xxx"]``：轻量盲审（默认）。
- ``cv-review --file <path> --mode debate [--rounds N]``：完整多轮闭环博弈。
"""

import argparse
import logging
import sys
from pathlib import Path

from cv_review.config import init_user_config
from cv_review.reviewer import review, debate

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    """配置全局日志级别与格式。

    Args:
        verbose: 若为 True，则启用 DEBUG 级别输出；否则为 INFO。
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_parser() -> argparse.ArgumentParser:
    """构建 ArgumentParser 实例。

    Returns:
        argparse.ArgumentParser: 配置完成的解析器。
    """
    parser = argparse.ArgumentParser(
        prog="cv-review",
        description="基于独立 API 盲审的文档交叉验证 CLI 工具。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="启用详细日志输出（DEBUG 级别）。",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # init 子命令
    init_parser = subparsers.add_parser(
        "init",
        help="在用户家目录生成 ~/.cv-review/ 配置模板。",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已有配置文件。",
    )

    # 评审参数（主命令默认行为）
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="待评审或博弈的文档路径（评审/博弈模式下必填）。",
    )
    parser.add_argument(
        "-i", "--instruction",
        type=str,
        default=None,
        help="追加的定向评审指令，如 '重点审查第三章并发模型'。",
    )
    parser.add_argument(
        "--mode",
        choices=["review", "debate"],
        default="review",
        help="评审模式：review（轻量盲审，默认）或 debate（完整多轮闭环）。",
    )
    parser.add_argument(
        "-r", "--rounds",
        type=int,
        default=2,
        metavar="N",
        help="debate 模式下的迭代轮数，默认 2。",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="outputs",
        help="debate 模式下输出目录，默认 outputs/。",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "json"],
        default="markdown",
        help="输出格式：markdown（默认）或 json。",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """cv-review 主入口。

    解析命令行参数，根据子命令或模式分发到对应的业务逻辑。

    Args:
        argv: 可选的命令行参数列表，默认使用 ``sys.argv[1:]``。

    Returns:
        int: 程序退出码，0 表示成功，1 表示发生可恢复错误。
    """
    # Windows 终端默认编码为 GBK，强制切换为 UTF-8 以正确显示中文
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    try:
        if args.command == "init":
            config_dir = init_user_config(force=args.force)
            print(f"[+] 配置模板已生成: {config_dir}")
            print("    请编辑该目录下的 api_settings.json 与 prompts.txt，")
            print("    并确保 Shell 环境变量中已配置对应 API Key。")
            return 0

        if not args.file:
            parser.print_help()
            print("\n错误: 必须提供 --file 参数，或使用 init 子命令。", file=sys.stderr)
            return 1

        if args.rounds < 1:
            print("[-] 错误: --rounds 必须为正整数", file=sys.stderr)
            return 1

        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"[-] 错误: 找不到文件 [{file_path}]", file=sys.stderr)
            return 1

        if args.mode == "review":
            feedback = review(
                str(file_path),
                instruction=args.instruction,
                output_format=args.output_format,
            )
            print(feedback)
            return 0

        if args.mode == "debate":
            output_path = debate(
                str(file_path),
                rounds=args.rounds,
                output_dir=args.output,
                output_format=args.output_format,
                instruction=args.instruction,
            )
            print(f"[+] 交叉验证完成，文档已输出至: {output_path}")
            return 0

        # 理论上不会到达此处，parser 已限制 mode 可选值
        parser.print_help()
        return 1

    except FileNotFoundError as exc:
        logger.error("文件未找到: %s", exc)
        print(f"[-] 错误: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        logger.error("输入无效: %s", exc)
        print(f"[-] 错误: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        logger.error("运行时错误: %s", exc)
        print(f"[-] 错误: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("未捕获的异常: %s", exc)
        print(f"[-] 未知错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
