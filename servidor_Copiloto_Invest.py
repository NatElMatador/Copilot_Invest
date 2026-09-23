import os
import json
import time
import threading
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from flask import Flask

# ================= CONFIGURAÇÕES DE NUVEM =================
QUIVER_TOKEN = os.environ.get("QUIVER_TOKEN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

POLITICOS_VIP = ["Nancy Pelosi"] 
ARQUIVO_DB = "carteira_pelosi.json"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Autopilot Avenue: Servidor Online, Seguro e Operacional!"
# ==========================================================

def carregar_db():
    if not os.path.exists(ARQUIVO_DB):
        db_inicial = {
            "caixa_disponivel": 0.0,
            "total_investido": 1000.0,
            "ativos": {"NVDA": 400.0, "AAPL": 300.0, "MSFT": 200.0, "AVGO": 100.0},
            "ultimo_trade_visto": ""
        }
        salvar_db(db_inicial)
        return db_inicial
    
    with open(ARQUIVO_DB, "r") as f:
        return json.load(f)

def salvar_db(dados):
    with open(ARQUIVO_DB, "w") as f:
        json.dump(dados, f, indent=4)

@bot.message_handler(commands=['start', 'ajuda'])
def enviar_ajuda(message):
    texto = (
        "🤖 **Autopilot Avenue Ativo**\n\n"
        "/setup - Injeta US$ 1000 no caixa (soma)\n"
        "/reset - Zera tudo e recomeça com US$ 1000 em caixa\n"
        "/resumo - Mostra o balanço da carteira\n"
        "/ajustar [texto] - Atualiza seus valores por voz/texto\n"
        "/analisar - Calcula defasagem e sugere realocações\n"
        "/buscar - Força varredura na Quiver"
    )
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(commands=['setup'])
def injetar_caixa(message):
    db = carregar_db()
    db["caixa_disponivel"] += 1000.0
    salvar_db(db)
    bot.send_message(message.chat.id, f"✅ US$ 1.000 adicionados. Saldo: US$ {db['caixa_disponivel']:.2f}.")

@bot.message_handler(commands=['reset'])
def resetar_carteira(message):
    db_limpo = {
        "caixa_disponivel": 1000.0,
        "total_investido": 0.0,
        "ativos": {},
        "ultimo_trade_visto": ""
    }
    salvar_db(db_limpo)
    bot.send_message(message.chat.id, "🔄 *Carteira Reiniciada com Sucesso!*\nVocê começou do zero. Tem agora exatamente US$ 1.000 em caixa livre e nenhum ativo na carteira.", parse_mode="Markdown")

@bot.message_handler(commands=['resumo'])
def mostrar_resumo(message):
    db = carregar_db()
    caixa = db.get("caixa_disponivel", 0.0)
    ativos = db.get("ativos", {})
    investido = sum(ativos.values())
    patrimonio_total = caixa + investido
    
    if patrimonio_total == 0:
        bot.send_message(message.chat.id, "Sua carteira está vazia.")
        return

    texto = f"📊 **FECHAMENTO DA CARTEIRA**\n\n"
    texto += f"💵 Patrimônio: US$ {patrimonio_total:.2f}\n"
    texto += f"🏦 Caixa Livre: US$ {caixa:.2f}\n\n**Alocação:**\n"
    
    for ticker, valor in ativos.items():
        percentual = (valor / patrimonio_total) * 100
        texto += f"• {ticker}: US$ {valor:.2f} ({percentual:.1f}%)\n"

    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(commands=['ajustar'])
def ajustar_por_voz(message):
    texto = message.text.replace("/ajustar", "").strip()
    if not texto:
        bot.send_message(message.chat.id, "Escreva como está sua conta. Exemplo:\n/ajustar Tenho 500 em Nvidia, 200 em Apple, 100 na Microsoft, zerei Broadcom e tenho 50 de caixa na Avenue.")
        return
    
    bot.send_message(message.chat.id, "🤖 Lendo seus dados com Inteligência Artificial...")
    
    prompt = f"""
    Extraia os valores financeiros deste texto do usuário.
    TEXTO: "{texto}"
    
    Regras:
    1. Identifique o valor em caixa (dinheiro livre). Se não for falado, use 0.0.
    2. Identifique as ações (traduza o nome da empresa para o Ticker correto da bolsa americana) e seus valores exatos em dólares.
    3. Responda APENAS com um JSON válido e limpo.
    
    Exemplo do formato de saída exigido:
    {{"caixa_disponivel": 50.0, "ativos": {{"NVDA": 500.0, "AAPL": 200.0, "MSFT": 100.0}}}}
    """
    
    try:
        resposta = client.models.generate_content(model='gemini-3.6-flash', contents=prompt).text.strip()
        
        # Limpeza robusta contra quebras de linha em Markdown
        resposta = resposta.replace("```json", "").replace("
