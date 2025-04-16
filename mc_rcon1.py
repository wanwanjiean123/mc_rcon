import os
from nonebot import on_command
from nonebot.adapters.qq import Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
from nonebot.permission import SUPERUSER
import mcrcon
from mcrcon import MCRcon
from dotenv import load_dotenv
from nonebot.utils import run_sync

# 加载 .env.pord 文件
load_dotenv(".env.prod")

__plugin_meta__ = PluginMetadata(
    name="Minecraft RCON 控制器 (mcrcon版)",
    description="通过QQ群控制Minecraft服务器的RCON插件",
    usage="""使用说明:
/cmd <命令> - 向Minecraft服务器发送命令
/list - 获取在线玩家列表
/wlist - 获取服务器白名单列表
/wladd <游戏ID> - 添加自己到白名单
/wlremove <游戏ID> - 从白名单移除玩家
""",
    type="application",
    supported_adapters={"~qq"},
)

# 从 .env.pord 读取配置
RCON_HOST = os.getenv("RCON_HOST", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "zz957957..")
SUPERUSER_IDS = os.getenv("SUPERUSER_IDS", "F7CE067628376D0FD5EAB88733A55408").split(",")

# 调试输出：检查 SUPERUSER_IDS 是否正确加载
SUPERUSER_IDS_RAW = os.getenv("SUPERUSER_IDS", "3399806248")  # 先获取原始字符串
logger.info(f"[DEBUG] SUPERUSER_IDS_RAW (from .env): {SUPERUSER_IDS_RAW}")

SUPERUSER_IDS = SUPERUSER_IDS_RAW.split(",")
logger.info(f"[DEBUG] SUPERUSER_IDS (parsed): {SUPERUSER_IDS}")

# 调试输出：检查当前环境变量
logger.info(f"[DEBUG] RCON_HOST: {RCON_HOST}")
logger.info(f"[DEBUG] RCON_PORT: {RCON_PORT}")
logger.info(f"[DEBUG] RCON_PASSWORD: {'*' * len(RCON_PASSWORD) if RCON_PASSWORD else 'None'}")  # 避免日志泄露密码


# 命令处理器（移除了权限限制）
cmd_handler = on_command("cmd", priority=5,permission=SUPERUSER)
list_handler = on_command("list", priority=5)
wlist_handler = on_command("wlist", priority=5)
wladd_handler = on_command("wladd", priority=5)
wlremove_handler = on_command("wlremove", priority=5)
kick_handler = on_command("kick", priority=5)
ban_handler = on_command("ban", priority=5)


def execute_rcon_command(command: str) -> str:
    """同步执行RCON命令（mcrcon需要同步调用）"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            return mcr.command(command)
    except Exception as e:
        logger.error(f"RCON命令失败: {e}")
        return f"命令执行错误: {str(e)}"


@cmd_handler.handle()
async def handle_cmd(event: MessageEvent, args: Message = CommandArg()):
    command = args.extract_plain_text().strip()
    if not command:
        await cmd_handler.finish("请输入命令，例如: /cmd say Hello")

    result = await run_sync(execute_rcon_command)(command)
    await cmd_handler.finish(f"🔄 执行结果:\n{result}")


@list_handler.handle()
async def handle_list():
    result = await run_sync(execute_rcon_command)("list")
    
    # 简单检查是否包含在线玩家信息
    if "online" not in result.lower():
        await list_handler.finish("🟡 无法获取玩家列表")
        return
    
    # 尝试解析玩家列表（静默处理错误）
    players_str = result.split(":")[1].strip() if ":" in result else ""
    all_players = [p.strip() for p in players_str.split(",") if p.strip()] if players_str else []
    
    # 分离普通玩家和假人(bot_前缀)
    online_players = [p for p in all_players if not p.startswith("bot_")]
    bot_players = [p for p in all_players if p.startswith("bot_")]
    
    # 序号字符集
    circle_numbers = ["①","②","③","④","⑤","⑥","⑦","⑧","⑨","⑩",
                     "⑪","⑫","⑬","⑭","⑮","⑯","⑰","⑱","⑲","⑳"]
    
    # 构建在线玩家列表
    output = "]在线玩家[\n"
    for i, player in enumerate(online_players, 1):
        number = circle_numbers[i-1] if i <= 20 else f"{i}."
        output += f"{number} {player}\n"
    
    # 添加分隔线
    output += "\n────────\n\n"
    
    # 构建假人列表
    output += "]假人列表[\n"
    for i, bot in enumerate(bot_players, 1):
        number = circle_numbers[i-1] if i <= 20 else f"{i}."
        output += f"{number} {bot}\n"
    
    if not online_players and not bot_players:
        output = "🟡 当前没有玩家在线"
    
    await list_handler.finish(output)



@wladd_handler.handle()
async def handle_wladd(event: MessageEvent, args: Message = CommandArg()):
    minecraft_id = args.extract_plain_text().strip()
    if not minecraft_id.isalnum() and "_" not in minecraft_id:
        await wladd_handler.finish("❌ ID只能包含字母、数字和下划线")

    result = await run_sync(execute_rcon_command)(f"whitelist add {minecraft_id}")
    if "added" in result.lower():
        await wladd_handler.finish(f"✅ 已添加 {minecraft_id} 到白名单")
    else:
        await wladd_handler.finish(f"❌ 添加失败: {result}")


@wlist_handler.handle()
async def handle_wlist():
    result = await run_sync(execute_rcon_command)("whitelist list")
    
    if "there are" not in result.lower():
        await wlist_handler.finish(f"🔴 获取失败:\n{result}")
        return
    
    # 提取玩家ID列表
    try:
        players_str = result.split(":")[1].strip()
        players = [p.strip() for p in players_str.split(",")]
    except Exception as e:
        logger.error(f"解析白名单失败: {e}")
        await wlist_handler.finish("❌ 解析白名单数据失败")
        return
    
    if not players:
        await wlist_handler.finish("🟡 白名单中没有玩家")
        return
    
    # 固定标题
    title = "]服务器白名单列表["
    
    # 序号字符集（①到⑳，超过20用数字）
    circle_numbers = ["①","②","③","④","⑤","⑥","⑦","⑧","⑨","⑩",
                     "⑪","⑫","⑬","⑭","⑮","⑯","⑰","⑱","⑲","⑳"]
    
    # 格式化输出
    output = f"{title}\n"
    for i, player in enumerate(players, 1):
        # 使用圆圈数字或普通数字
        if i <= 20:
            number = circle_numbers[i-1]
        else:
            number = f"{i}."
        output += f"{number} {player}\n"
    
    await wlist_handler.finish(output)



@wlremove_handler.handle()
async def handle_wlremove(event: MessageEvent, args: Message = CommandArg()):
    minecraft_id = args.extract_plain_text().strip()
    if not minecraft_id.isalnum() and "_" not in minecraft_id:
        await wlremove_handler.finish("❌ ID只能包含字母、数字和下划线")

    result = await run_sync(execute_rcon_command)(f"whitelist remove {minecraft_id}")
    if "removed" in result.lower():
        await wlremove_handler.finish(f"✅ 已从白名单移除 {minecraft_id}")
    else:
        await wlremove_handler.finish(f"❌ 移除失败: {result}")


