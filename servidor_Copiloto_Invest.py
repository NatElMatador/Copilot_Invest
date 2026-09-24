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
        resposta = resposta.replace("```json", "").replace("```", "").strip()
            
        novos_dados = json.loads(resposta)
        
        db = carregar_db()
        db["caixa_disponivel"] = float(novos_dados.get("caixa_disponivel", 0.0))
        db["ativos"] = novos_dados.get("ativos", {})
        db["total_investido"] = sum(db["ativos"].values())
        salvar_db(db)
        
        bot.send_message(message.chat.id, "✅ *Valores atualizados com sucesso!*\nEnvie o comando /analisar para calcularmos a sua defasagem.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ *Não consegui extrair os valores com precisão.* Tente escrever de forma mais direta (Ex: /ajustar NVDA 400, AAPL 200, Caixa 100).", parse_mode="Markdown")

@bot.message_handler(commands=['analisar'])
def analisar_defasagem(message):
    db = carregar_db()
    caixa = db.get("caixa_disponivel", 0.0)
    ativos = db.get("ativos", {})
    patrimonio = caixa + sum(ativos.values())
    
    if patrimonio == 0:
        bot.send_message(message.chat.id, "Sua carteira está vazia.")
        return
        
    ALVO = {"NVDA": 0.40, "AAPL": 0.30, "MSFT": 0.20, "AVGO": 0.10}
    
    texto = f"⚖️ **ANÁLISE DE DEFASAGEM (ALVO PELOSI)**\n"
    texto += f"💵 Patrimônio Total: US$ {patrimonio:.2f}\n"
    texto += f"🏦 Caixa Livre: US$ {caixa:.2f}\n\n"
    
    sugestoes = []
    
    for ticker, percentual in ALVO.items():
        ideal = patrimonio * percentual
        atual = ativos.get(ticker, 0.0)
        diff = ideal - atual
        
        texto += f"• **{ticker}** | Atual: US$ {atual:.2f} 🎯 Ideal: US$ {ideal:.2f}\n"
        
        if diff > 10:
            texto += f"   📉 Faltam US$ {diff:.2f}\n"
            sugestoes.append(f"🟢 COMPRAR US$ {diff:.2f} de {ticker}")
        elif diff < -10:
            texto += f"   📈 Excesso de US$ {abs(diff):.2f}\n"
            sugestoes.append(f"🔴 VENDER US$ {abs(diff):.2f} de {ticker}")
        else:
            texto += f"   ✅ Perfeitamente alinhado!\n"
            
    texto += "\n**🛠️ PLANO DE REALOCAÇÃO RECOMENDADO:**\n"
    if sugestoes:
        texto += "\n".join(sugestoes)
        if caixa < sum([diff for ticker, diff in ALVO.items() if (patrimonio * diff) - ativos.get(ticker, 0.0) > 10]):
            texto += "\n\n⚠️ *Aviso: O seu caixa livre não cobre todas as compras necessárias. Comece executando as ordens de VENDA para gerar liquidez antes de comprar o que falta.*"
    else:
        texto += "Perfeito! Nenhuma movimentação é necessária hoje."
        
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

def disparar_alerta_interativo(trade, valor_aporte):
    ticker = trade.get('Ticker', 'Desconhecido')
    prompt = f"Crie um alerta VERDE curto com emojis informando a compra de {ticker} pela Nancy Pelosi. Valor do aporte recomendado: US$ {valor_aporte}. Use apenas negrito (**)."
    
    resposta = client.models.generate_content(model='gemini-3.6-flash', contents=prompt).text.strip()
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Executado na Avenue", callback_data=f"COMPRAR_{ticker}_{valor_aporte}"))
    markup.add(InlineKeyboardButton("❌ Ignorado", callback_data="IGNORAR"))

    bot.send_message(CHAT_ID, resposta, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def processar_clique(call):
    acao = call.data
    if acao == "IGNORAR":
        bot.edit_message_text("❌ *Ignorado.* O banco de dados não foi alterado.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        return

    if acao.startswith("COMPRAR"):
        _, ticker, valor_str = acao.split("_")
        valor_aporte = float(valor_str)
        db = carregar_db()
        
        if db.get("caixa_disponivel", 0.0) < valor_aporte:
            bot.answer_callback_query(call.id, "Saldo insuficiente no caixa virtual!")
            return
            
        db["caixa_disponivel"] -= valor_aporte
        if "ativos" not in db:
            db["ativos"] = {}
            
        if ticker in db["ativos"]:
            db["ativos"][ticker] += valor_aporte
        else:
            db["ativos"][ticker] = valor_aporte
            
        salvar_db(db)
        bot.edit_message_text(f"✅ *Compra de US$ {valor_aporte} de {ticker} registrada com sucesso!*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")

def varredura_quiver():
    url = "https://api.quiverquant.com/beta/live/congresstrading"
    headers = {"Authorization": f"Token {QUIVER_TOKEN}", "Accept": "application/json"}
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        if resposta.status_code == 200:
            for trade in resposta.json():
                politico = trade.get('Representative', '')
                ticker = trade.get('Ticker', '')
                operacao = trade.get('Transaction', '')
                trade_id = f"{politico}_{ticker}_{trade.get('ReportDate', '')}_{operacao}"
                
                if any(vip in politico for vip in POLITICOS_VIP) and operacao == "Purchase":
                    db = carregar_db()
                    if db.get("ultimo_trade_visto") != trade_id:
                        db["ultimo_trade_visto"] = trade_id
                        salvar_db(db)
                        disparar_alerta_interativo(trade, 50.0)
                    return 
    except Exception as e:
        print(f"Erro na varredura da Quiver: {e}")

@bot.message_handler(commands=['buscar'])
def forcar_busca(message):
    bot.send_message(message.chat.id, "Iniciando varredura manual na Quiver...")
    varredura_quiver()

def loop_continuo_quiver():
    while True:
        varredura_quiver()
        time.sleep(3600)

def iniciar_telegram():
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            time.sleep(15)

if TELEGRAM_TOKEN and GEMINI_API_KEY:
    carregar_db()
    threading.Thread(target=loop_continuo_quiver, daemon=True).start()
    threading.Thread(target=iniciar_telegram, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
