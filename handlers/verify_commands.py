"""验证命令处理器"""
import asyncio
import logging
import httpx
import time
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import VERIFY_COST
from database_mysql import Database
from one.sheerid_verifier import SheerIDVerifier as OneVerifier
from k12.sheerid_verifier import SheerIDVerifier as K12Verifier
from spotify.sheerid_verifier import SheerIDVerifier as SpotifyVerifier
from youtube.sheerid_verifier import SheerIDVerifier as YouTubeVerifier
from Boltnew.sheerid_verifier import SheerIDVerifier as BoltnewVerifier
from military.sheerid_verifier import (
    SheerIDVerifier as MilitaryVerifier,
    create_verification_from_token,
    extract_access_token,
    diagnose_token,
    test_token_quick
)
from utils.messages import get_insufficient_balance_message, get_verify_usage_message

# 尝试导入并发控制，如果失败则使用空实现
try:
    from utils.concurrency import get_verification_semaphore
except ImportError:
    # 如果导入失败，创建一个简单的实现
    def get_verification_semaphore(verification_type: str):
        return asyncio.Semaphore(3)

logger = logging.getLogger(__name__)


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /verify 命令 - Gemini One Pro"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    if not context.args:
        await update.message.reply_text(
            get_verify_usage_message("/verify", "Gemini One Pro")
        )
        return

    url = context.args[0]
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    verification_id = OneVerifier.parse_verification_id(url)
    if not verification_id:
        await update.message.reply_text("无效的 SheerID 链接，请检查后重试。")
        return

    if not db.deduct_balance(user_id, VERIFY_COST):
        await update.message.reply_text("扣除积分失败，请稍后重试。")
        return

    processing_msg = await update.message.reply_text(
        f"开始处理 Gemini One Pro 认证...\n"
        f"验证ID: {verification_id}\n"
        f"已扣除 {VERIFY_COST} 积分\n\n"
        "请稍候，这可能需要 1-2 分钟..."
    )

    try:
        verifier = OneVerifier(verification_id)
        result = await asyncio.to_thread(verifier.verify)

        db.add_verification(
            user_id,
            "gemini_one_pro",
            url,
            "success" if result["success"] else "failed",
            str(result),
        )

        if result["success"]:
            result_msg = "✅ 认证成功！\n\n"
            if result.get("pending"):
                result_msg += "文档已提交，等待人工审核。\n"
            if result.get("redirect_url"):
                result_msg += f"跳转链接：\n{result['redirect_url']}"
            await processing_msg.edit_text(result_msg)
        else:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 认证失败：{result.get('message', '未知错误')}\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
    except Exception as e:
        logger.error("验证过程出错: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ 处理过程中出现错误：{str(e)}\n\n"
            f"已退回 {VERIFY_COST} 积分"
        )


async def verify2_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /verify2 命令 - ChatGPT Teacher K12"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    if not context.args:
        await update.message.reply_text(
            get_verify_usage_message("/verify2", "ChatGPT Teacher K12")
        )
        return

    url = context.args[0]
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    verification_id = K12Verifier.parse_verification_id(url)
    if not verification_id:
        await update.message.reply_text("无效的 SheerID 链接，请检查后重试。")
        return

    if not db.deduct_balance(user_id, VERIFY_COST):
        await update.message.reply_text("扣除积分失败，请稍后重试。")
        return

    processing_msg = await update.message.reply_text(
        f"开始处理 ChatGPT Teacher K12 认证...\n"
        f"验证ID: {verification_id}\n"
        f"已扣除 {VERIFY_COST} 积分\n\n"
        "请稍候，这可能需要 1-2 分钟..."
    )

    try:
        verifier = K12Verifier(verification_id)
        result = await asyncio.to_thread(verifier.verify)

        db.add_verification(
            user_id,
            "chatgpt_teacher_k12",
            url,
            "success" if result["success"] else "failed",
            str(result),
        )

        if result["success"]:
            result_msg = "✅ 认证成功！\n\n"
            if result.get("pending"):
                result_msg += "文档已提交，等待人工审核。\n"
            if result.get("redirect_url"):
                result_msg += f"跳转链接：\n{result['redirect_url']}"
            await processing_msg.edit_text(result_msg)
        else:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 认证失败：{result.get('message', '未知错误')}\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
    except Exception as e:
        logger.error("验证过程出错: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ 处理过程中出现错误：{str(e)}\n\n"
            f"已退回 {VERIFY_COST} 积分"
        )


async def verify3_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /verify3 命令 - Spotify Student"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    if not context.args:
        await update.message.reply_text(
            get_verify_usage_message("/verify3", "Spotify Student")
        )
        return

    url = context.args[0]
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    # 解析 verificationId
    verification_id = SpotifyVerifier.parse_verification_id(url)
    if not verification_id:
        await update.message.reply_text("无效的 SheerID 链接，请检查后重试。")
        return

    if not db.deduct_balance(user_id, VERIFY_COST):
        await update.message.reply_text("扣除积分失败，请稍后重试。")
        return

    processing_msg = await update.message.reply_text(
        f"🎵 开始处理 Spotify Student 认证...\n"
        f"已扣除 {VERIFY_COST} 积分\n\n"
        "📝 正在生成学生信息...\n"
        "🎨 正在生成学生证 PNG...\n"
        "📤 正在提交文档..."
    )

    # 使用信号量控制并发
    semaphore = get_verification_semaphore("spotify_student")

    try:
        async with semaphore:
            verifier = SpotifyVerifier(verification_id)
            result = await asyncio.to_thread(verifier.verify)

        db.add_verification(
            user_id,
            "spotify_student",
            url,
            "success" if result["success"] else "failed",
            str(result),
        )

        if result["success"]:
            result_msg = "✅ Spotify 学生认证成功！\n\n"
            if result.get("pending"):
                result_msg += "✨ 文档已提交，等待 SheerID 审核\n"
                result_msg += "⏱️ 预计审核时间：几分钟内\n\n"
            if result.get("redirect_url"):
                result_msg += f"🔗 跳转链接：\n{result['redirect_url']}"
            await processing_msg.edit_text(result_msg)
        else:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 认证失败：{result.get('message', '未知错误')}\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
    except Exception as e:
        logger.error("Spotify 验证过程出错: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ 处理过程中出现错误：{str(e)}\n\n"
            f"已退回 {VERIFY_COST} 积分"
        )


async def verify4_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /verify4 命令 - Bolt.new Teacher（自动获取code版）"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    if not context.args:
        await update.message.reply_text(
            get_verify_usage_message("/verify4", "Bolt.new Teacher")
        )
        return

    url = context.args[0]
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    # 解析 externalUserId 或 verificationId
    external_user_id = BoltnewVerifier.parse_external_user_id(url)
    verification_id = BoltnewVerifier.parse_verification_id(url)

    if not external_user_id and not verification_id:
        await update.message.reply_text("无效的 SheerID 链接，请检查后重试。")
        return

    if not db.deduct_balance(user_id, VERIFY_COST):
        await update.message.reply_text("扣除积分失败，请稍后重试。")
        return

    processing_msg = await update.message.reply_text(
        f"🚀 开始处理 Bolt.new Teacher 认证...\n"
        f"已扣除 {VERIFY_COST} 积分\n\n"
        "📤 正在提交文档..."
    )

    # 使用信号量控制并发
    semaphore = get_verification_semaphore("bolt_teacher")

    try:
        async with semaphore:
            # 第1步：提交文档
            verifier = BoltnewVerifier(url, verification_id=verification_id)
            result = await asyncio.to_thread(verifier.verify)

        if not result.get("success"):
            # 提交失败，退款
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 文档提交失败：{result.get('message', '未知错误')}\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
            return
        
        vid = result.get("verification_id", "")
        if not vid:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 未获取到验证ID\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
            return
        
        # 更新消息
        await processing_msg.edit_text(
            f"✅ 文档已提交！\n"
            f"📋 验证ID: `{vid}`\n\n"
            f"🔍 正在自动获取认证码...\n"
            f"（最多等待20秒）"
        )
        
        # 第2步：自动获取认证码（最多20秒）
        code = await _auto_get_reward_code(vid, max_wait=20, interval=5)
        
        if code:
            # 成功获取
            result_msg = (
                f"🎉 认证成功！\n\n"
                f"✅ 文档已提交\n"
                f"✅ 审核已通过\n"
                f"✅ 认证码已获取\n\n"
                f"🎁 认证码: `{code}`\n"
            )
            if result.get("redirect_url"):
                result_msg += f"\n🔗 跳转链接:\n{result['redirect_url']}"
            
            await processing_msg.edit_text(result_msg)
            
            # 保存成功记录
            db.add_verification(
                user_id,
                "bolt_teacher",
                url,
                "success",
                f"Code: {code}",
                vid
            )
        else:
            # 20秒内未获取到，让用户稍后查询
            await processing_msg.edit_text(
                f"✅ 文档已提交成功！\n\n"
                f"⏳ 认证码尚未生成（可能需要1-5分钟审核）\n\n"
                f"📋 验证ID: `{vid}`\n\n"
                f"💡 请稍后使用以下命令查询:\n"
                f"`/getV4Code {vid}`\n\n"
                f"注意：积分已消耗，稍后查询无需再付费"
            )
            
            # 保存待处理记录
            db.add_verification(
                user_id,
                "bolt_teacher",
                url,
                "pending",
                "Waiting for review",
                vid
            )
            
    except Exception as e:
        logger.error("Bolt.new 验证过程出错: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ 处理过程中出现错误：{str(e)}\n\n"
            f"已退回 {VERIFY_COST} 积分"
        )


async def _auto_get_reward_code(
    verification_id: str,
    max_wait: int = 20,
    interval: int = 5
) -> Optional[str]:
    """自动获取认证码（轻量级轮询，不影响并发）
    
    Args:
        verification_id: 验证ID
        max_wait: 最大等待时间（秒）
        interval: 轮询间隔（秒）
        
    Returns:
        str: 认证码，如果获取失败返回None
    """
    import time
    start_time = time.time()
    attempts = 0
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            elapsed = int(time.time() - start_time)
            attempts += 1
            
            # 检查是否超时
            if elapsed >= max_wait:
                logger.info(f"自动获取code超时({elapsed}秒)，让用户手动查询")
                return None
            
            try:
                # 查询验证状态
                response = await client.get(
                    f"https://my.sheerid.com/rest/v2/verification/{verification_id}"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    current_step = data.get("currentStep")
                    
                    if current_step == "success":
                        # 获取认证码
                        code = data.get("rewardCode") or data.get("rewardData", {}).get("rewardCode")
                        if code:
                            logger.info(f"✅ 自动获取code成功: {code} (耗时{elapsed}秒)")
                            return code
                    elif current_step == "error":
                        # 审核失败
                        logger.warning(f"审核失败: {data.get('errorIds', [])}")
                        return None
                    # else: pending，继续等待
                
                # 等待下次轮询
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.warning(f"查询认证码出错: {e}")
                await asyncio.sleep(interval)
    
    return None


async def verify5_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /verify5 命令 - YouTube Student Premium"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    if not context.args:
        await update.message.reply_text(
            get_verify_usage_message("/verify5", "YouTube Student Premium")
        )
        return

    url = context.args[0]
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    # 解析 verificationId
    verification_id = YouTubeVerifier.parse_verification_id(url)
    if not verification_id:
        await update.message.reply_text("无效的 SheerID 链接，请检查后重试。")
        return

    if not db.deduct_balance(user_id, VERIFY_COST):
        await update.message.reply_text("扣除积分失败，请稍后重试。")
        return

    processing_msg = await update.message.reply_text(
        f"📺 开始处理 YouTube Student Premium 认证...\n"
        f"已扣除 {VERIFY_COST} 积分\n\n"
        "📝 正在生成学生信息...\n"
        "🎨 正在生成学生证 PNG...\n"
        "📤 正在提交文档..."
    )

    # 使用信号量控制并发
    semaphore = get_verification_semaphore("youtube_student")

    try:
        async with semaphore:
            verifier = YouTubeVerifier(verification_id)
            result = await asyncio.to_thread(verifier.verify)

        db.add_verification(
            user_id,
            "youtube_student",
            url,
            "success" if result["success"] else "failed",
            str(result),
        )

        if result["success"]:
            result_msg = "✅ YouTube Student Premium 认证成功！\n\n"
            if result.get("pending"):
                result_msg += "✨ 文档已提交，等待 SheerID 审核\n"
                result_msg += "⏱️ 预计审核时间：几分钟内\n\n"
            if result.get("redirect_url"):
                result_msg += f"🔗 跳转链接：\n{result['redirect_url']}"
            await processing_msg.edit_text(result_msg)
        else:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ 认证失败：{result.get('message', '未知错误')}\n\n"
                f"已退回 {VERIFY_COST} 积分"
            )
    except Exception as e:
        logger.error("YouTube 验证过程出错: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ 处理过程中出现错误：{str(e)}\n\n"
            f"已退回 {VERIFY_COST} 积分"
        )


async def getV4Code_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """处理 /getV4Code 命令 - 获取 Bolt.new Teacher 认证码"""
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("您已被拉黑，无法使用此功能。")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("请先使用 /start 注册。")
        return

    # 检查是否提供了 verification_id
    if not context.args:
        await update.message.reply_text(
            "使用方法: /getV4Code <verification_id>\n\n"
            "示例: /getV4Code 6929436b50d7dc18638890d0\n\n"
            "verification_id 在使用 /verify4 命令后会返回给您。"
        )
        return

    verification_id = context.args[0].strip()

    processing_msg = await update.message.reply_text(
        "🔍 正在查询认证码，请稍候..."
    )

    try:
        # 查询 SheerID API 获取认证码
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://my.sheerid.com/rest/v2/verification/{verification_id}"
            )

            if response.status_code != 200:
                await processing_msg.edit_text(
                    f"❌ 查询失败，状态码：{response.status_code}\n\n"
                    "请稍后重试或联系管理员。"
                )
                return

            data = response.json()
            current_step = data.get("currentStep")
            reward_code = data.get("rewardCode") or data.get("rewardData", {}).get("rewardCode")
            redirect_url = data.get("redirectUrl")

            if current_step == "success" and reward_code:
                result_msg = "✅ 认证成功！\n\n"
                result_msg += f"🎉 认证码：`{reward_code}`\n\n"
                if redirect_url:
                    result_msg += f"跳转链接：\n{redirect_url}"
                await processing_msg.edit_text(result_msg)
            elif current_step == "pending":
                await processing_msg.edit_text(
                    "⏳ 认证仍在审核中，请稍后再试。\n\n"
                    "通常需要 1-5 分钟，请耐心等待。"
                )
            elif current_step == "error":
                error_ids = data.get("errorIds", [])
                await processing_msg.edit_text(
                    f"❌ 认证失败\n\n"
                    f"错误信息：{', '.join(error_ids) if error_ids else '未知错误'}"
                )
            else:
                await processing_msg.edit_text(
                    f"⚠️ 当前状态：{current_step}\n\n"
                    "认证码尚未生成，请稍后重试。"
                )

    except Exception as e:
        logger.error("获取 Bolt.new 认证码失败: %s", e)
        await processing_msg.edit_text(
            f"❌ 查询过程中出现错误：{str(e)}\n\n"
            "请稍后重试或联系管理员。"
        )


async def verify6_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Handle /verify6 command - ChatGPT Military Verification
    
    Supports multiple modes:
    1. SheerID Link mode: /verify6 <sheerid_link> [email] (RECOMMENDED - most reliable)
    2. Auth Token mode: /verify6 <accessToken> [email] (may fail due to CloudFlare)
    3. Diagnostic mode: /verify6 test <token> (test if token works)
    
    Optional email parameter:
    - If provided, your email will be used (you'll receive verification link)
    - If omitted, random email will be generated
    """
    user_id = update.effective_user.id

    if db.is_user_blocked(user_id):
        await update.message.reply_text("You have been blocked from using this service.")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("Please use /start to register first.")
        return

    if not context.args:
        await update.message.reply_text(
            "🎖️ **ChatGPT Military Verification**\n\n"
            "**Method 1 (RECOMMENDED):** SheerID Link\n"
            "```\n/verify6 <SheerID_link> [email]\n```\n\n"
            "**How to get SheerID link:**\n"
            "1. Go to https://chatgpt.com/veterans-claim\n"
            "2. Click 'Verify my status'\n"
            "3. Copy URL from browser (starts with services.sheerid.com)\n\n"
            "**With Your Email:**\n"
            "```\n/verify6 <link> yourname@gmail.com\n```\n"
            "✅ You'll receive verification link in your inbox\n\n"
            "**Method 2:** Auth Token (may not work)\n"
            "```\n/verify6 <accessToken> [email]\n```\n\n"
            "**Test Token:**\n"
            "```\n/verify6 test <accessToken>\n```\n\n"
            "This verification is for US Military Veterans.",
            parse_mode="Markdown"
        )
        return

    # Check for diagnostic/test mode
    if context.args[0].lower() == "test" and len(context.args) > 1:
        token_input = " ".join(context.args[1:])
        access_token = extract_access_token(token_input)
        
        if not access_token:
            await update.message.reply_text(
                "❌ Could not extract token from input.\n"
                "Token should start with 'eyJ...' (JWT format)"
            )
            return
        
        processing_msg = await update.message.reply_text(
            "🔍 **Testing Token...**\n\n"
            f"Token length: {len(access_token)}\n"
            f"Preview: `{access_token[:30]}...`\n\n"
            "⏳ Checking endpoints...",
            parse_mode="Markdown"
        )
        
        # Run diagnostic
        diag_result = await asyncio.to_thread(diagnose_token, access_token)
        
        status_lines = []
        for endpoint, info in diag_result.get("endpoints_status", {}).items():
            status = info.get("status", "?")
            ok = "✅" if info.get("ok") else "❌"
            status_lines.append(f"{ok} {endpoint}: {status}")
        
        await processing_msg.edit_text(
            "🔍 **Token Diagnostic Results**\n\n"
            f"Token valid: {'✅ Yes' if diag_result['valid'] else '❌ No'}\n"
            f"Token length: {diag_result['token_length']}\n"
            f"Is JWT: {'✅' if diag_result['is_jwt'] else '❌'}\n\n"
            "**Endpoint Status:**\n" + "\n".join(status_lines) + "\n\n" +
            (f"⚠️ Error: {diag_result['error']}\n\n" if diag_result.get('error') else "") +
            ("✅ Token works! You can use it for verification.\n" if diag_result['valid'] else 
             "❌ Token not working. Get a fresh one from:\n"
             "https://chatgpt.com/api/auth/session\n\n"
             "Or use SheerID link method (recommended)."),
            parse_mode="Markdown"
        )
        return

    input_text = " ".join(context.args)  # Handle multi-word input
    user = db.get_user(user_id)
    if user["balance"] < VERIFY_COST:
        await update.message.reply_text(
            get_insufficient_balance_message(user["balance"])
        )
        return

    # Extract email if provided (check for email pattern)
    user_email = None
    args_to_process = list(context.args)
    
    # Check last argument for email pattern
    if len(args_to_process) > 1:
        potential_email = args_to_process[-1]
        if '@' in potential_email and '.' in potential_email:
            user_email = potential_email
            args_to_process = args_to_process[:-1]  # Remove email from args
            input_text = " ".join(args_to_process)
            logger.info(f"User provided email: {user_email}")

    verification_id = None
    is_token_mode = False
    
    # First check if it's a SheerID link (PREFERRED method)
    if "sheerid.com" in input_text.lower() or "verificationId=" in input_text:
        verification_id = MilitaryVerifier.parse_verification_id(input_text)
        if verification_id:
            is_token_mode = False
            processing_msg = await update.message.reply_text(
                f"🎖️ **ChatGPT Military Verification**\n\n"
                f"✅ SheerID link detected!\n"
                f"🆔 ID: `{verification_id[:20]}...`\n\n"
                f"⏳ Starting verification process...\n"
                f"💰 Will deduct {VERIFY_COST} points",
                parse_mode="Markdown"
            )
    
    # If not a link, try to extract access token
    if not verification_id:
        access_token = extract_access_token(input_text)
        
        if access_token:
            is_token_mode = True
            processing_msg = await update.message.reply_text(
                "🎖️ **ChatGPT Military Verification**\n\n"
                "🔑 Auth token detected!\n"
                "⏳ Testing token validity...",
                parse_mode="Markdown"
            )
            
            # Quick token test first
            token_valid = await asyncio.to_thread(test_token_quick, access_token)
            
            if not token_valid:
                await processing_msg.edit_text(
                    "❌ **Token appears to be invalid or expired**\n\n"
                    "The token failed authentication check.\n\n"
                    "**Please use the SheerID link method instead:**\n"
                    "1. Go to https://chatgpt.com/veterans-claim\n"
                    "2. Click 'Verify my status'\n"
                    "3. Copy the URL from browser\n"
                    "4. Use: `/verify6 <URL>`\n\n"
                    "Or get a fresh token from:\n"
                    "https://chatgpt.com/api/auth/session",
                    parse_mode="Markdown"
                )
                return
            
            await processing_msg.edit_text(
                "🎖️ **ChatGPT Military Verification**\n\n"
                "✅ Token valid!\n"
                "⏳ Creating verification ID...",
                parse_mode="Markdown"
            )
            
            # Create verification ID from token
            verification_id = await asyncio.to_thread(
                create_verification_from_token, access_token
            )
            
            if not verification_id:
                await processing_msg.edit_text(
                    "❌ **Failed to create verification from token**\n\n"
                    "🔒 ChatGPT API blocked the request.\n\n"
                    "**Use the SheerID link method instead:**\n"
                    "1. Go to https://chatgpt.com/veterans-claim\n"
                    "2. Click 'Verify my status'\n"
                    "3. When SheerID page opens, copy the URL\n"
                    "4. Use: `/verify6 <URL>`\n\n"
                    "**URL format:**\n"
                    "`https://services.sheerid.com/verify/...?verificationId=...`",
                    parse_mode="Markdown"
                )
                return
            
            await processing_msg.edit_text(
                f"🎖️ **ChatGPT Military Verification**\n\n"
                f"✅ Verification created from token!\n"
                f"🆔 ID: `{verification_id[:20]}...`\n\n"
                f"⏳ Starting verification process...",
                parse_mode="Markdown"
            )
        else:
            # Neither link nor token
            await update.message.reply_text(
                "❌ **Invalid input!**\n\n"
                "Could not detect SheerID link or access token.\n\n"
                "**Please provide one of:**\n"
                "• SheerID link (recommended)\n"
                "• Access token (starts with 'eyJ...')\n\n"
                "Use `/verify6` for help.",
                parse_mode="Markdown"
            )
            return

    # Deduct balance
    if not db.deduct_balance(user_id, VERIFY_COST):
        await processing_msg.edit_text("Failed to deduct points, please try again later.")
        return

    # Use semaphore for concurrency control
    semaphore = get_verification_semaphore("chatgpt_military")

    try:
        # Update message to show email info
        if user_email:
            await processing_msg.edit_text(
                f"{processing_msg.text}\n\n"
                f"📧 Using your email: `{user_email}`\n"
                f"✉️ You'll receive verification link in inbox",
                parse_mode="Markdown"
            )
        
        async with semaphore:
            verifier = MilitaryVerifier(verification_id)
            # Pass user_email to verification (will use for all attempts)
            result = await asyncio.to_thread(
                verifier.verify, 
                auto_retry=True, 
                max_retries=15,  # Updated to match new default
                email=user_email
            )

        db.add_verification(
            user_id,
            "chatgpt_military",
            f"token:{verification_id}" if is_token_mode else input_text,
            "success" if result["success"] else "failed",
            str(result),
        )

        if result["success"]:
            result_msg = "✅ ChatGPT Military verification submitted!\n\n"
            if is_token_mode:
                result_msg += "🔑 Mode: Auth Token\n"
            if user_email:
                result_msg += f"📧 Email: {user_email}\n"
            if result.get("veteran_name"):
                result_msg += f"👤 Veteran: {result['veteran_name']}\n"
            if result.get("branch"):
                result_msg += f"🏛️ Branch: {result['branch']}\n"
            if result.get("attempts"):
                result_msg += f"🔄 Attempts: {result['attempts']}\n"
            if result.get("success_rate"):
                result_msg += f"📊 Success Rate: {result['success_rate']:.1f}%\n"
            if result.get("pending"):
                result_msg += "\n✨ Information submitted, awaiting SheerID review\n"
                result_msg += "⏱️ Estimated review time: A few minutes\n"
                if user_email:
                    result_msg += f"📬 Check your inbox: {user_email}\n"
            if result.get("reward_code"):
                result_msg += f"\n🎉 Reward Code: `{result['reward_code']}`\n"
            if result.get("redirect_url"):
                result_msg += f"\n🔗 Redirect link:\n{result['redirect_url']}"
            await processing_msg.edit_text(result_msg, parse_mode="Markdown")
        else:
            db.add_balance(user_id, VERIFY_COST)
            await processing_msg.edit_text(
                f"❌ Verification failed: {result.get('message', 'Unknown error')}\n\n"
                f"Refunded {VERIFY_COST} points"
            )
    except Exception as e:
        logger.error("Military verification error: %s", e)
        db.add_balance(user_id, VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ Error during processing: {str(e)}\n\n"
            f"Refunded {VERIFY_COST} points"
        )



