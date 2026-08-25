import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import yt_dlp as youtube_dl
from googletrans import Translator

# 환경변수 로드
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 번역 클라이언트 (googletrans - 무료!)
translator = Translator()

# ========== 번역 기능 ==========
@bot.command(name='tr')
async def translate(ctx, target_lang='ko', *, text):
    """
    번역 명령어
    사용법: !tr [언어코드] [텍스트]
    예: !tr ko hello (영어를 한국어로)
    언어코드: ko(한국어), ja(일본어), en(영어), es(스페인어), fr(프랑스어)
    """
    try:
        async with ctx.typing():
            result = translator.translate(text, src_language='auto', dest_language=target_lang)
            translated = result['text']
            detected_lang = result['src']
            
            embed = discord.Embed(
                title="📝 번역 결과",
                color=discord.Color.blue()
            )
            embed.add_field(name="원본 (감지됨)", value=f"{text}\n({detected_lang})", inline=False)
            embed.add_field(name="번역 결과", value=translated, inline=False)
            embed.add_field(name="대상 언어", value=target_lang, inline=False)
            
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ 번역 오류: {str(e)}")

# ========== 음악 재생 기능 ==========
youtube_dl.utils.bug_reports_message = lambda: ''

ydl_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, 
            lambda: youtube_dl.YoutubeDL(ydl_options).extract_info(url, download=False)
        )
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url']
        return cls(
            discord.FFmpegPCMAudio(
                filename, 
                **{
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
                    'options': '-vn'
                }
            ), 
            data=data
        )

@bot.command(name='play')
async def play(ctx, *, query):
    """
    노래 재생 명령어
    사용법: !play [곡명 또는 아티스트]
    예: !play Shape of You Ed Sheeran
    """
    try:
        # 봇이 음성 채널에 연결되어 있는지 확인
        if not ctx.author.voice:
            await ctx.send("❌ 음성 채널에 먼저 접속해주세요!")
            return
        
        channel = ctx.author.voice.channel
        
        # 이미 연결되어 있으면 그대로, 아니면 연결
        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
        
        # YouTube에서 검색
        await ctx.send(f"🔍 검색 중: `{query}`...")
        
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: youtube_dl.YoutubeDL(ydl_options).extract_info(query, download=False)
        )
        
        if 'entries' not in data or len(data['entries']) == 0:
            await ctx.send("❌ 곡을 찾을 수 없습니다.")
            return
        
        song = data['entries'][0]
        url = song['webpage_url']
        
        # 음악 재생
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=loop)
            ctx.voice_client.play(
                player,
                after=lambda e: print(f'Player error: {e}') if e else None
            )
        
        embed = discord.Embed(
            title="🎵 재생 중",
            description=song.get('title', '알 수 없음'),
            color=discord.Color.green()
        )
        embed.add_field(name="채널", value=song.get('uploader', '알 수 없음'), inline=False)
        duration = song.get('duration', 0)
        embed.add_field(name="길이", value=f"{duration//60}분 {duration%60}초", inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {str(e)}")

@bot.command(name='stop')
async def stop(ctx):
    """음악 중지"""
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏹️ 음악이 중지되었습니다.")
    else:
        await ctx.send("❌ 재생 중인 음악이 없습니다.")

@bot.command(name='pause')
async def pause(ctx):
    """음악 일시정지"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ 음악이 일시정지되었습니다.")
    else:
        await ctx.send("❌ 재생 중인 음악이 없습니다.")

@bot.command(name='resume')
async def resume(ctx):
    """음악 재개"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ 음악이 재개되었습니다.")
    else:
        await ctx.send("❌ 일시정지된 음악이 없습니다.")

@bot.command(name='disconnect')
async def disconnect(ctx):
    """음성 채널 나가기"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 음성 채널에서 나갔습니다.")
    else:
        await ctx.send("❌ 음성 채널에 접속하지 않았습니다.")

# ========== 기본 이벤트 ==========
@bot.event
async def on_ready():
    print(f'{bot.user}로 로그인했습니다!')
    await bot.change_presence(activity=discord.Game(name="!help로 명령어 확인"))

@bot.command(name='help')
async def help_command(ctx):
    """도움말"""
    embed = discord.Embed(
        title="🤖 디스코드 봇 명령어",
        description="한/일/영 번역 + 음악 재생 봇",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="📝 번역 기능",
        value="`!tr [언어코드] [텍스트]`\n예: `!tr ko hello`\n언어: ko(한국어), ja(일본어), en(영어), es(스페인어), fr(프랑스어)",
        inline=False
    )
    embed.add_field(
        name="🎵 음악 재생",
        value="`!play [곡명]` - 곡 재생\n`!pause` - 일시정지\n`!resume` - 재개\n`!stop` - 중지\n`!disconnect` - 음성 채널 나가기",
        inline=False
    )
    embed.set_footer(text="먼저 음성 채널에 접속하세요!")
    await ctx.send(embed=embed)

# 봇 실행
if __name__ == '__main__':
    bot.run(TOKEN)
