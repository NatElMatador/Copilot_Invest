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

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

ARQUIVO_DB = "carteira_pelosi.json"

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Autopilot Avenue: Servidor Online, Seguro e Operacional!"
# ==========================================================

def carregar_db():
    if not os.path.exists(ARQUIVO_DB):
        db_inicial = {
            "caixa_disponivel": 1000.0,
            "total_investido": 0.0,
            "ativos": {},
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
        "🤖 **Autopilot Avenue: Fundo Quantitativo do Congresso**\n\n"
        "**Gestão Mensal:**\n"
        "/analisar - Calcula a defasagem da sua carteira contra o TOP 50 do Congresso\n"
        "/ajustar [texto] - Atualiza seus saldos/aportes por voz ou texto livre\n"
        "/resumo - Mostra o balanço atual do seu portfólio\n\n"
        "**Inteligência de Mercado:**\n"
        "/perguntar [sua dúvida] - IA responde lendo a API da Quiver ao vivo\n\n"
        "**Administração:**\n"
        "/setup - Injeta US$ 1000 adicionais no caixa virtual\n"
        "/reset - Zera a carteira para US$ 1000 em caixa"
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
    texto += f"🏦 Caixa Livre: US$ {caixa:.2f}\n\n**Alocação Atual:**\n"
    
    ativos_ordenados = sorted(ativos.items(), key=lambda x: x[1], reverse=True)
    for ticker, valor in ativos_ordenados:
        if valor > 0.1: # Esconde poeira
            percentual = (valor / patrimonio_total) * 100
            texto += f"• {ticker}: US$ {valor:.2f} ({percentual:.1f}%)\n"

    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(commands=['ajustar'])
def ajustar_por_voz(message):
    texto = message.text.replace("/ajustar", "").strip()
    if not texto:
        bot.send_message(message.chat.id, "Escreva como está sua conta. Exemplo:\n/ajustar Fiz um aporte e meu caixa agora é 200. Tenho 450 em NVDA, 200 em AAPL e 150 em MSFT.")
        return
    
    bot.send_message(message.chat.id, "🤖 Lendo seus dados com Inteligência Artificial...")
    
    prompt = f"""
    Extraia os valores financeiros deste texto do usuário.
    TEXTO: "{texto}"
    Regras:
    1. Identifique o valor em caixa (dinheiro livre).
    2. Identifique as ações pelo Ticker correto e seus valores em dólares.
    3. Responda APENAS com um JSON válido e limpo, sem marcações markdown.
    Exemplo: {{"caixa_disponivel": 200.0, "ativos": {{"NVDA": 450.0, "AAPL": 200.0}}}}
    """
    
    try:
        resposta = client.models.generate_content(model='gemini-3.6-flash', contents=prompt).text.strip()
        resposta = resposta.replace("```json", "").replace("```", "").strip()
        novos_dados = json.loads(resposta)
        
        db = carregar_db()
        db["caixa_disponivel"] = float(novos_dados.get("caixa_disponivel", 0.0))
        db["ativos"] = novos_dados.get("ativos", {})
        db["total_investido"] = sum(db["ativos"].values())
        salvar_db(db)
        
        bot.send_message(message.chat.id, "✅ *Valores atualizados!* Envie /analisar para calcular o rebalanceamento mensal.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ *Erro ao processar o texto.* Tente um formato direto: /ajustar Caixa 100, NVDA 200.", parse_mode="Markdown")

@bot.message_handler(commands=['perguntar'])
def responder_pergunta(message):
    pergunta = message.text.replace("/perguntar", "").strip()
    if not pergunta:
        bot.send_message(message.chat.id, "Qual a sua dúvida? Ex: /perguntar Quais foram as 3 ações mais compradas pelo Senado esta semana?")
        return

    bot.send_message(message.chat.id, "🔍 Acessando a API da Quiver e processando a estratégia com IA...")

    url = "https://api.quiverquant.com/beta/live/congresstrading"
    headers = {"Authorization": f"Token {QUIVER_TOKEN}", "Accept": "application/json"}
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        # Pega as últimas 150 movimentações para dar contexto rico à IA sem estourar limite
        dados_api = resposta.json()[:150] 

        prompt = f"""
        Você é um analista quantitativo auxiliando um cirurgião oncológico que investe a longo prazo.
        Use os dados brutos recentes de transações do Congresso Americano abaixo para responder à pergunta.
        
        Pergunta do usuário: {pergunta}
        
        Dados brutos do Congresso: {json.dumps(dados_api)}
        
        Responda de forma analítica, direta e profissional em português. Use negrito para tickers e valores.
        """
        resposta_ia = client.models.generate_content(model='gemini-3.6-flash', contents=prompt).text.strip()
        bot.send_message(message.chat.id, resposta_ia, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro de comunicação com a API: {e}")

@bot.message_handler(commands=['analisar'])
def analisar_mensal_top50(message):
    bot.send_message(message.chat.id, "📊 Baixando centenas de movimentações do Congresso e calculando o peso do TOP 50. Isso leva alguns segundos...")
    
    url = "https://api.quiverquant.com/beta/live/congresstrading"
    headers = {"Authorization": f"Token {QUIVER_TOKEN}", "Accept": "application/json"}
    
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        trades = resposta.json()
        
        # 1. Somar o volume financeiro estimado por Ticker (Apenas Compras)
        volumes_compra = {}
        for trade in trades:
            if trade.get('Transaction') == 'Purchase':
                ticker = trade.get('Ticker')
                if not ticker: continue
                
                amount_str = str(trade.get('Amount', '0'))
                valor_piso = 0
                if "$" in amount_str:
                    try:
                        # Pega o piso da faixa (Ex: $15,001 - $50,000 -> 15001)
                        parte_limpa = amount_str.split('-')[0].replace('$', '').replace(',', '').strip()
                        if parte_limpa.lower() != 'unknown':
                            valor_piso = float(parte_limpa)
                    except:
                        valor_piso = 0
                
                # Se o valor não estiver na faixa, estimamos $10k como piso padrão para não descartar
                if valor_piso == 0: valor_piso = 10000 
                volumes_compra[ticker] = volumes_compra.get(ticker, 0) + valor_piso
        
        # 2. Isolar as TOP 50 maiores ações de convicção
        top50 = sorted(volumes_compra.items(), key=lambda x: x[1], reverse=True)[:50]
        volume_total_top50 = sum([v for k, v in top50])
        
        if volume_total_top50 == 0:
            bot.send_message(message.chat.id, "Nenhuma compra registrada recentemente.")
            return

        # 3. Criar a "fatia ideal" de cada ação baseada no peso do dinheiro
        alvo_percentual = {ticker: (volume / volume_total_top50) for ticker, volume in top50}
        
        # 4. Avaliar contra a carteira do usuário
        db = carregar_db()
        caixa = db.get("caixa_disponivel", 0.0)
        ativos_atuais = db.get("ativos", {})
        patrimonio = caixa + sum(ativos_atuais.values())
        
        if patrimonio == 0:
            bot.send_message(message.chat.id, "Sua carteira está vazia. Use /setup para adicionar capital.")
            return

        texto_ordens = "🛠️ **PLANO DE EXECUÇÃO MENSAL:**\n\n"
        ordens_venda = []
        ordens_compra = []
        
        # Verificar o que precisa comprar (dentro das Top 50)
        for ticker, percentual in alvo_percentual.items():
            ideal = patrimonio * percentual
            atual = ativos_atuais.get(ticker, 0.0)
            diff = ideal - atual
            
            # Só sugere se a diferença for maior que 10 dólares (evita poeira)
            if diff > 10:
                ordens_compra.append(f"🟢 COMPRAR US$ {diff:.2f} de **{ticker}**")
            elif diff < -10:
                ordens_venda.append(f"🔴 VENDER US$ {abs(diff):.2f} de **{ticker}**")

        # Limpar o que não faz mais parte do Top 50
        for ticker, atual in ativos_atuais.items():
            if ticker not in alvo_percentual and atual > 10:
                ordens_venda.append(f"🔴 LIQUIDAR TODO O ATIVO: US$ {atual:.2f} de **{ticker}** (Saiu do Top 50)")

        if not ordens_venda and not ordens_compra:
            bot.send_message(message.chat.id, "✅ Sua carteira está perfeitamente alinhada com o TOP 50 do Congresso!")
            return

        # Montar a mensagem de saída limpa
        texto_ordens += "*ORDENS DE VENDA (Geração de Caixa)*\n"
        texto_ordens += "\n".join(ordens_venda) if ordens_venda else "Nenhuma venda necessária."
        texto_ordens += "\n\n*ORDENS DE COMPRA (Alocação)*\n"
        
        # Limitamos a exibição das compras às maiores diferenças para caber na tela do celular
        if ordens_compra:
            texto_ordens += "\n".join(ordens_compra[:20]) 
            if len(ordens_compra) > 20:
                texto_ordens += f"\n... e outras {len(ordens_compra)-20} micro-posições. (Foque nas principais acima)."
        else:
            texto_ordens += "Nenhuma compra necessária."

        bot.send_message(message.chat.id, texto_ordens, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao calcular rebalanceamento: {e}")

def varredura_quiver_baleias():
    # Esta função roda em silêncio de hora em hora. Ela NÃO pede pra você comprar,
    # serve apenas como um "Alerta de Tubarão" (Compras acima de US$ 250.000)
    url = "https://api.quiverquant.com/beta/live/congresstrading"
    headers = {"Authorization": f"Token {QUIVER_TOKEN}", "Accept": "application/json"}
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        if resposta.status_code == 200:
            for trade in resposta.json():
                politico = trade.get('Representative', 'Alguém')
                ticker = trade.get('Ticker', '')
                operacao = trade.get('Transaction', '')
                trade_id = f"{politico}_{ticker}_{trade.get('ReportDate', '')}_{operacao}"
                
                if operacao == "Purchase":
                    amount_str = str(trade.get('Amount', '0'))
                    valor_piso = 0
                    if "$" in amount_str:
                        try:
                            valor_piso = float(amount_str.split('-')[0].replace('$', '').replace(',', '').strip())
                        except: pass
                    
                    # Alerta situacional massivo (Membro do congresso injetou > 250k dólares)
                    if valor_piso >= 250000:
                        db = carregar_db()
                        if db.get("ultimo_trade_visto") != trade_id:
                            db["ultimo_trade_visto"] = trade_id
                            salvar_db(db)
                            
                            texto = f"🚨 **ALERTA DE BALEIA NO CONGRESSO** 🚨\n\n{politico} acabou de investir mais de **US$ {valor_piso:,.0f}** na ação **{ticker}**.\n*(Isto é apenas um alerta de radar. Sua alocação é feita mensalmente via /analisar)*"
                            bot.send_message(CHAT_ID, texto, parse_mode="Markdown")
                        return 
    except Exception as e:
        print(f"Erro na varredura: {e}")

def loop_continuo_quiver():
    while True:
        varredura_quiver_baleias()
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