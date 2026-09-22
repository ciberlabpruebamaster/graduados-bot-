import os
import hmac
import hashlib
import time
import threading
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
PHONE_NUMBER_ID_2 = os.environ.get("PHONE_NUMBER_ID_2", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Asesoría Laboral")
BASE_URL = os.environ.get("BASE_URL", "")

# Configuración email
GMAIL_USER = os.environ.get("GMAIL_USER", "javier.martin.ruiz.gs@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ASESOR_EMAIL = os.environ.get("ASESOR_EMAIL", "rrss.nebulosadigital@gmail.com")

TIMEOUT_MINUTES = 10

user_state: dict[str, dict] = {}
user_state_2: dict[str, dict] = {}

# ── BOT 1: FLUJOS LABORALES ───────────────────────────────────────────

FLOWS = {
    "1": {
        "name": "Nóminas y Contratos",
        "intro": "📋 Perfecto. Para orientarte bien necesito hacerte 3 preguntas rápidas.",
        "questions": [
            "¿Eres empresa o trabajador?\n\nA) Empresa o autónomo con empleados\nB) Trabajador por cuenta ajena",
            "¿Qué necesitas exactamente?\n\nA) Elaborar o revisar nóminas\nB) Redactar o revisar un contrato\nC) Calcular finiquito o liquidación\nD) Regularización de atrasos o diferencias salariales",
            "¿Con qué urgencia lo necesitas?\n\nA) Urgente (esta semana)\nB) Sin prisa (en 2-3 semanas)",
        ],
        "closing": (
            "✅ Perfecto, con esto ya tengo lo que necesito.\n\n"
            "¿Me dices tu *nombre* y un *email o teléfono* para que el asesor "
            "te prepare la documentación y se ponga en contacto contigo?"
        ),
    },
    "2": {
        "name": "Altas y Bajas en Seguridad Social",
        "intro": "🏛️ Entendido. Unas preguntas rápidas para gestionar tu trámite.",
        "questions": [
            "¿Qué trámite necesitas?\n\nA) Alta de trabajador en empresa\nB) Baja de trabajador en empresa\nC) Alta como autónomo (RETA)\nD) Baja como autónomo (RETA)\nE) Variación de datos o jornada",
            "¿Para cuándo lo necesitas?\n\nA) Urgente (hoy o mañana)\nB) Esta semana\nC) Sin prisa",
            "¿Tienes la documentación del trabajador o tuya lista?\n\nA) Sí, tengo todo\nB) No, necesito saber qué documentos hacen falta",
        ],
        "closing": (
            "✅ Anotado. Dame tu *nombre* y un *email o teléfono* "
            "y lo gestionamos cuanto antes."
        ),
    },
    "3": {
        "name": "Prestaciones y Subsidios",
        "intro": "💶 De acuerdo. Vamos a ver a qué prestación puedes tener derecho.",
        "questions": [
            "¿Qué tipo de prestación te interesa?\n\nA) Desempleo (paro)\nB) Incapacidad temporal (baja médica)\nC) Jubilación o prejubilación\nD) Maternidad / paternidad / excedencia\nE) Otra (viudedad, orfandad, ingreso mínimo vital...)",
            "¿Eres...?\n\nA) Trabajador por cuenta ajena\nB) Autónomo/a",
            "¿Ya tienes alguna solicitud iniciada?\n\nA) No, quiero empezar desde cero\nB) Sí, tengo una en trámite y tengo dudas",
        ],
        "closing": (
            "✅ Perfecto. Dame tu *nombre* y un *email o teléfono* "
            "y el asesor te llama para explicarte los pasos y los plazos."
        ),
    },
    "4": {
        "name": "Inspección de Trabajo",
        "intro": "⚖️ Entendido. La Inspección de Trabajo requiere actuar con rapidez. Cuéntame:",
        "questions": [
            "¿Cuál es tu situación?\n\nA) He recibido una visita de inspección\nB) Me han llegado requerimientos o propuesta de sanción\nC) Quiero interponer una denuncia\nD) Consulta preventiva (quiero saber si cumplo la normativa)",
            "¿Hay algún plazo urgente que debas cumplir?\n\nA) Sí, tengo plazo en menos de 7 días\nB) No, es una consulta sin urgencia inmediata",
        ],
        "closing": (
            "✅ Recibido. Dame tu *nombre* y un *email o teléfono* "
            "y el asesor se pone en contacto contigo a la mayor brevedad."
        ),
    },
    "5": {
        "name": "Asesoría Laboral General",
        "intro": "📞 Cuéntame. Dos preguntas para dirigirte al asesor adecuado.",
        "questions": [
            "¿Sobre qué tema es tu consulta?\n\nA) Despido o extinción de contrato\nB) Modificación de condiciones de trabajo\nC) Convenio colectivo aplicable\nD) Reclamación de salarios\nE) Otra consulta laboral",
            "¿Eres...?\n\nA) Empresa o empleador\nB) Trabajador/a",
        ],
        "closing": (
            "✅ Anotado. Dame tu *nombre* y un *email o teléfono* "
            "y te atendemos lo antes posible."
        ),
    },
}

WELCOME_MESSAGE = (
    f"👋 ¡Hola! Soy el asistente de *{BUSINESS_NAME}*.\n\n"
    "Te ayudo con todos tus trámites laborales y de Seguridad Social de forma rápida y sencilla.\n\n"
    "¿En qué puedo ayudarte hoy?\n\n"
    "1️⃣ Nóminas y Contratos\n"
    "2️⃣ Altas y Bajas en Seguridad Social\n"
    "3️⃣ Prestaciones y Subsidios\n"
    "4️⃣ Inspección de Trabajo\n"
    "5️⃣ Asesoría Laboral General\n"
    "6️⃣ Hablar con el asesor\n"
    "7️⃣ Solicitar una llamada"
)

# ── BOT 2: SERVICIOS JURÍDICOS ────────────────────────────────────────

FLOWS2 = {
    "1": {
        "name": "Asesoramiento Fiscal",
        "image": "fiscal.png",
        "options": (
            "A) Planificación Societaria\n"
            "B) IRPF y Renta\n"
            "C) Patrimonio y Sucesiones\n"
            "D) Impuesto de Sociedades\n"
            "E) Subvenciones y Licencias"
        ),
    },
    "2": {
        "name": "Asesoramiento Laboral",
        "image": "laboral_ases.png",
        "options": (
            "A) Nóminas y Contratos\n"
            "B) Seguridad Social\n"
            "C) Prestaciones y Subsidios\n"
            "D) Inspección de Trabajo\n"
            "E) Asesoría General"
        ),
    },
    "3": {
        "name": "Derecho de Circulación",
        "image": "circulacion.png",
        "options": (
            "A) Accidentes de Tráfico\n"
            "B) Reclamaciones\n"
            "C) Delitos de Tráfico\n"
            "D) Transporte\n"
            "E) Peritaciones"
        ),
    },
    "4": {
        "name": "Derecho Civil",
        "image": "civil.png",
        "options": (
            "A) Procesos Civiles\n"
            "B) Arrendamientos\n"
            "C) Derecho de Familia\n"
            "D) Derecho Sucesorio\n"
            "E) Propiedad Intelectual"
        ),
    },
    "5": {
        "name": "Derecho Deportivo",
        "image": "deportivo.png",
        "options": (
            "A) Laboral Deportivo\n"
            "B) Fiscal Deportivo\n"
            "C) Asesoramiento a Clubes\n"
            "D) Litigios Deportivos\n"
            "E) Federaciones y Asociaciones"
        ),
    },
    "6": {
        "name": "Derecho de Extranjería",
        "image": "extranjeria.png",
        "options": (
            "A) Residencia y NIE\n"
            "B) Arraigo\n"
            "C) Visados\n"
            "D) Nacionalidad\n"
            "E) Recursos"
        ),
    },
    "7": {
        "name": "Derecho Laboral",
        "image": "laboral.png",
        "options": (
            "A) Contratación y Despidos\n"
            "B) Jurisdicción Social\n"
            "C) Prestaciones Sociales\n"
            "D) EREs y Reestructuración\n"
            "E) Permisos y Excedencias"
        ),
    },
    "8": {
        "name": "Derecho Mercantil",
        "image": "mercantil.png",
        "options": (
            "A) Sociedades\n"
            "B) Fusiones y Adquisiciones\n"
            "C) Derecho de Seguros\n"
            "D) Situaciones de Crisis\n"
            "E) Contratos Mercantiles"
        ),
    },
    "9": {
        "name": "Derecho Urbanismo",
        "image": "urbanismo.png",
        "options": (
            "A) Planeamiento Urbanístico\n"
            "B) Expropiaciones\n"
            "C) Expedientes\n"
            "D) Licencias\n"
            "E) Disciplina Urbanística"
        ),
    },
}

WELCOME_MESSAGE_2 = (
    f"👋 ¡Hola! Soy el asistente jurídico de *{BUSINESS_NAME}*.\n\n"
    "¿En qué área podemos ayudarte?\n\n"
    "1️⃣ Asesoramiento Fiscal\n"
    "2️⃣ Asesoramiento Laboral\n"
    "3️⃣ Derecho de Circulación\n"
    "4️⃣ Derecho Civil\n"
    "5️⃣ Derecho Deportivo\n"
    "6️⃣ Derecho de Extranjería\n"
    "7️⃣ Derecho Laboral\n"
    "8️⃣ Derecho Mercantil\n"
    "9️⃣ Derecho Urbanismo"
)

# ── MENSAJES COMUNES ──────────────────────────────────────────────────

OUT_OF_HOURS_MESSAGE = (
    "⏰ En este momento estamos fuera de horario. "
    "Atendemos de *lunes a viernes de 9:00 a 18:00h*.\n\n"
    "Tu consulta ha quedado registrada. El asesor te responderá en cuanto abramos.\n\n"
    "Si lo prefieres, déjanos tu nombre y teléfono y te llamamos a primera hora. 📞"
)

TIMEOUT_REMINDER = (
    "¿Sigues ahí? 😊 Puedes continuar cuando quieras "
    "o escribe *MENU* para volver al inicio."
)

INVALID_OPTION = (
    "No reconozco esa opción. Por favor elige entre:\n\n"
    "1️⃣ Nóminas y Contratos\n"
    "2️⃣ Altas y Bajas en Seguridad Social\n"
    "3️⃣ Prestaciones y Subsidios\n"
    "4️⃣ Inspección de Trabajo\n"
    "5️⃣ Asesoría Laboral General\n"
    "6️⃣ Hablar con el asesor\n"
    "7️⃣ Solicitar una llamada\n\n"
    "O escribe *MENU* en cualquier momento para volver aquí."
)

INVALID_OPTION_2 = (
    "No reconozco esa opción. Por favor elige un número del 1 al 9:\n\n"
    "1️⃣ Asesoramiento Fiscal\n"
    "2️⃣ Asesoramiento Laboral\n"
    "3️⃣ Derecho de Circulación\n"
    "4️⃣ Derecho Civil\n"
    "5️⃣ Derecho Deportivo\n"
    "6️⃣ Derecho de Extranjería\n"
    "7️⃣ Derecho Laboral\n"
    "8️⃣ Derecho Mercantil\n"
    "9️⃣ Derecho Urbanismo\n\n"
    "O escribe *MENU* para volver aquí."
)


# ── UTILIDADES ────────────────────────────────────────────────────────

def is_business_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 18


def send_whatsapp_message(to: str, text: str, phone_number_id: str = None) -> None:
    pid = phone_number_id or PHONE_NUMBER_ID
    url = f"https://graph.facebook.com/v20.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending message to {to}: {e}")


def send_whatsapp_image(to: str, image_filename: str, caption: str = "", phone_number_id: str = None) -> None:
    pid = phone_number_id or PHONE_NUMBER_ID_2
    url = f"https://graph.facebook.com/v20.0/{pid}/messages"
    image_url = f"{BASE_URL}/static/servicios/{image_filename}"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending image to {to}: {e}")


def send_email(subject: str, body: str) -> None:
    """Envía un email desde GMAIL_USER a ASESOR_EMAIL."""
    if not GMAIL_APP_PASSWORD:
        print("GMAIL_APP_PASSWORD no configurada — email no enviado")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = ASESOR_EMAIL
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:     
            server.ehlo()     
            server.starttls()    
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, ASESOR_EMAIL, msg.as_string())
        print(f"Email enviado a {ASESOR_EMAIL}: {subject}")
    except Exception as e:
        print(f"Error enviando email: {e}")


def notify_asesor(service_name: str, answers: list, contact_info: str, user_phone: str) -> None:
    answers_text = "\n".join([f"  • R{i + 1}: {a}" for i, a in enumerate(answers)])
    subject = f"[{BUSINESS_NAME}] NUEVO CLIENTE — {service_name}"
    body = (
        f"NUEVO CLIENTE — {service_name}\n"
        f"{'=' * 50}\n\n"
        f"WhatsApp cliente: +{user_phone}\n"
        f"Datos de contacto: {contact_info}\n\n"
        f"Respuestas del cuestionario:\n{answers_text}\n"
    )
    send_email(subject, body)


def notify_asesor_simple(reason: str, info: str, user_phone: str) -> None:
    subject = f"[{BUSINESS_NAME}] {reason}"
    body = (
        f"{reason}\n"
        f"{'=' * 50}\n\n"
        f"WhatsApp cliente: +{user_phone}\n"
        f"{info}\n"
    )
    send_email(subject, body)


def notify_asesor_2(area: str, subopcion: str, contact_info: str, user_phone: str) -> None:
    subject = f"[{BUSINESS_NAME}] NUEVA CONSULTA JURÍDICA — {area}"
    body = (
        f"NUEVA CONSULTA JURÍDICA\n"
        f"{'=' * 50}\n\n"
        f"WhatsApp cliente: +{user_phone}\n"
        f"Área: {area}\n"
        f"Subopción: {subopcion}\n"
        f"Datos de contacto: {contact_info}\n"
    )
    send_email(subject, body)


# ── ESTADO ────────────────────────────────────────────────────────────

def init_state(user_id: str) -> dict:
    state: dict = {
        "step": "menu",
        "service_key": None,
        "q_index": 0,
        "answers": [],
        "last_activity": datetime.now(),
        "timeout_sent": False,
    }
    user_state[user_id] = state
    return state


def get_state(user_id: str) -> dict:
    if user_id not in user_state:
        return init_state(user_id)
    return user_state[user_id]


def init_state_2(user_id: str) -> dict:
    state: dict = {
        "step": "menu2",
        "area_key": None,
        "subopcion": None,
        "last_activity": datetime.now(),
        "timeout_sent": False,
    }
    user_state_2[user_id] = state
    return state


def get_state_2(user_id: str) -> dict:
    if user_id not in user_state_2:
        return init_state_2(user_id)
    return user_state_2[user_id]


def is_menu_keyword(text: str) -> bool:
    return text.strip().lower() in {
        "menu", "menú", "inicio", "start",
        "hola", "hi", "hello", "buenas",
        "buenos días", "buenas tardes", "hey",
    }


# ── LÓGICA BOT 1 ──────────────────────────────────────────────────────

def handle_message(user_id: str, text: str) -> None:
    text_clean = text.strip()
    state = get_state(user_id)
    state["last_activity"] = datetime.now()
    state["timeout_sent"] = False

    if is_menu_keyword(text_clean):
        init_state(user_id)
        send_whatsapp_message(user_id, WELCOME_MESSAGE)
        return

    step = state["step"]

    if step == "menu":
        if text_clean in ("1", "2", "3", "4", "5"):
            flow = FLOWS[text_clean]
            state["step"] = "flow_q"
            state["service_key"] = text_clean
            state["q_index"] = 0
            state["answers"] = []
            send_whatsapp_message(user_id, f"{flow['intro']}\n\n{flow['questions'][0]}")

        elif text_clean == "6":
            state["step"] = "s6_query"
            send_whatsapp_message(
                user_id,
                "💬 El asesor puede estar atendiendo a otros clientes en este momento.\n\n"
                "Deja tu *nombre* y cuéntame brevemente tu consulta, "
                "y se pondrá en contacto contigo en cuanto pueda.",
            )

        elif text_clean == "7":
            state["step"] = "s7_time"
            send_whatsapp_message(
                user_id,
                "📞 Sin problema. ¿Cuándo te viene mejor que te llamemos?\n\n"
                "A) Esta mañana\n"
                "B) Esta tarde\n"
                "C) Mañana a primera hora\n"
                "D) Indicar otro horario",
            )

        else:
            send_whatsapp_message(user_id, INVALID_OPTION)

    elif step == "flow_q":
        flow = FLOWS[state["service_key"]]
        state["answers"].append(text_clean)
        next_idx = state["q_index"] + 1

        if next_idx < len(flow["questions"]):
            state["q_index"] = next_idx
            send_whatsapp_message(user_id, flow["questions"][next_idx])
        else:
            state["step"] = "flow_contact"
            send_whatsapp_message(user_id, flow["closing"])

    elif step == "flow_contact":
        flow = FLOWS[state["service_key"]]
        notify_asesor(flow["name"], state["answers"], text_clean, user_id)
        send_whatsapp_message(
            user_id,
            "✅ ¡Perfecto! El asesor revisará tu solicitud y te contactará en menos de 24 horas. 😊\n\n"
            "Si necesitas algo más escribe *MENU*.",
        )
        init_state(user_id)

    elif step == "s6_query":
        notify_asesor_simple("QUIERE HABLAR CON EL ASESOR", text_clean, user_id)
        send_whatsapp_message(
            user_id,
            "✅ Recibido. El asesor te contactará en cuanto pueda. 😊\n\n"
            "Si necesitas algo más escribe *MENU*.",
        )
        init_state(user_id)

    elif step == "s7_time":
        state["answers"] = [f"Horario preferido: {text_clean}"]
        state["step"] = "s7_contact"
        send_whatsapp_message(
            user_id,
            "📋 Anotado. ¿Me dices tu *nombre* y un *teléfono* para llamarte?",
        )

    elif step == "s7_contact":
        horario = state["answers"][0] if state["answers"] else "No especificado"
        notify_asesor_simple(
            "SOLICITA LLAMADA",
            f"Contacto: {text_clean} — {horario}",
            user_id,
        )
        send_whatsapp_message(
            user_id,
            "✅ ¡Perfecto! Te llamamos en el horario indicado. 😊\n\n"
            "Si necesitas algo más escribe *MENU*.",
        )
        init_state(user_id)


# ── LÓGICA BOT 2 ──────────────────────────────────────────────────────

def handle_message_2(user_id: str, text: str) -> None:
    text_clean = text.strip().upper()
    state = get_state_2(user_id)
    state["last_activity"] = datetime.now()
    state["timeout_sent"] = False

    if is_menu_keyword(text_clean.lower()):
        init_state_2(user_id)
        send_whatsapp_message(user_id, WELCOME_MESSAGE_2, PHONE_NUMBER_ID_2)
        return

    step = state["step"]

    if step == "menu2":
        key = text_clean
        if key in FLOWS2:
            flow = FLOWS2[key]
            state["step"] = "flow2_sub"
            state["area_key"] = key
            send_whatsapp_image(user_id, flow["image"], phone_number_id=PHONE_NUMBER_ID_2)
            send_whatsapp_message(
                user_id,
                f"Estas son las áreas de *{flow['name']}* en las que podemos ayudarte:\n\n"
                f"{flow['options']}\n\n"
                "¿Cuál es tu caso?",
                PHONE_NUMBER_ID_2,
            )
        else:
            send_whatsapp_message(user_id, INVALID_OPTION_2, PHONE_NUMBER_ID_2)

    elif step == "flow2_sub":
        flow = FLOWS2[state["area_key"]]
        state["subopcion"] = f"{text_clean} — {flow['name']}"
        state["step"] = "flow2_contact"
        send_whatsapp_message(
            user_id,
            "✅ Entendido.\n\n"
            "Para que nuestro asesor se ponga en contacto contigo, "
            "dinos tu *nombre completo* y un *teléfono o email*.",
            PHONE_NUMBER_ID_2,
        )

    elif step == "flow2_contact":
        flow = FLOWS2[state["area_key"]]
        notify_asesor_2(flow["name"], state["subopcion"], text_clean, user_id)
        send_whatsapp_message(
            user_id,
            "✅ ¡Perfecto! Hemos recibido tu consulta.\n\n"
            "Nuestro asesor se pondrá en contacto contigo en menos de 24 horas. 😊\n\n"
            "Si necesitas algo más escribe *MENU*.",
            PHONE_NUMBER_ID_2,
        )
        init_state_2(user_id)


# ── TIMEOUT ───────────────────────────────────────────────────────────

def timeout_checker() -> None:
    while True:
        time.sleep(60)
        now = datetime.now()
        for user_id, state in list(user_state.items()):
            if state["step"] == "menu" or state.get("timeout_sent"):
                continue
            elapsed = (now - state["last_activity"]).total_seconds() / 60
            if elapsed >= TIMEOUT_MINUTES:
                send_whatsapp_message(user_id, TIMEOUT_REMINDER)
                state["timeout_sent"] = True
        for user_id, state in list(user_state_2.items()):
            if state["step"] == "menu2" or state.get("timeout_sent"):
                continue
            elapsed = (now - state["last_activity"]).total_seconds() / 60
            if elapsed >= TIMEOUT_MINUTES:
                send_whatsapp_message(user_id, TIMEOUT_REMINDER, PHONE_NUMBER_ID_2)
                state["timeout_sent"] = True


threading.Thread(target=timeout_checker, daemon=True).start()


# ── WEBHOOK ───────────────────────────────────────────────────────────

def verify_signature(payload: bytes, signature: str) -> bool:
    if not APP_SECRET:
        return True
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    if APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(request.data, signature):
            return "Unauthorized", 401

    data = request.get_json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return jsonify({"status": "ok"}), 200

        message = value["messages"][0]
        from_number = message["from"]
        message_type = message.get("type")
        incoming_phone_id = value.get("metadata", {}).get("phone_number_id", "")

        if message_type != "text":
            pid = PHONE_NUMBER_ID_2 if incoming_phone_id == PHONE_NUMBER_ID_2 else PHONE_NUMBER_ID
            send_whatsapp_message(
                from_number,
                "Solo proceso texto por ahora 😊 Escribe *MENU* para ver las opciones.",
                pid,
            )
            return jsonify({"status": "ok"}), 200

        user_text = message["text"]["body"]

        # Enrutar según número receptor
        if incoming_phone_id == PHONE_NUMBER_ID_2:
            if from_number not in user_state_2:
                init_state_2(from_number)
                send_whatsapp_message(from_number, WELCOME_MESSAGE_2, PHONE_NUMBER_ID_2)
                return jsonify({"status": "ok"}), 200
            handle_message_2(from_number, user_text)
        else:
            if from_number not in user_state:
                init_state(from_number)
                send_whatsapp_message(from_number, WELCOME_MESSAGE)
                return jsonify({"status": "ok"}), 200

            state = user_state[from_number]
            if (
                state["step"] == "menu"
                and not is_menu_keyword(user_text)
                and not is_business_hours()
            ):
                send_whatsapp_message(from_number, OUT_OF_HOURS_MESSAGE)
                return jsonify({"status": "ok"}), 200

            handle_message(from_number, user_text)

    except (KeyError, IndexError) as e:
        print(f"Webhook parse error: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running", "bot": f"{BUSINESS_NAME} WhatsApp Bot v1"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
