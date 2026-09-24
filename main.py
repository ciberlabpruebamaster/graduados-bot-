import os
import hmac
import hashlib
import time
import threading
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Asesoría Graduados")
BASE_URL = os.environ.get("BASE_URL", "")

# Configuración email (Resend)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
ASESOR_EMAIL = os.environ.get("ASESOR_EMAIL", "rrss.nebulosadigital@gmail.com")

TIMEOUT_MINUTES = 10

user_state: dict[str, dict] = {}

# ── FLUJOS LABORALES ──────────────────────────────────────────────────

FLOWS = {
    "1": {
        "name": "Nóminas y Contratos",
        "intro": "📋 Perfecto. Para orientarte bien necesito hacerte 3 preguntas rápidas.",
        "questions": [
            "¿Eres empresa o trabajador?\n\nA) Empresa o autónomo con empleados\nB) Trabajador por cuenta ajena",
            "¿Qué necesitas exactamente?\n\nA) Elaborar o revisar nóminas\nB) Redactar o revisar un contrato\nC) Calcular finiquito o liquidación\nD) Regularización de atrasos o diferencias salariales",
            "¿Con qué urgencia lo necesitas?\n\nA) Urgente (esta semana)\nB) Sin prisa (en 2-3 semanas)",
        ],
        "options": [
            {"a": "Empresa o autónomo con empleados", "b": "Trabajador por cuenta ajena"},
            {"a": "Elaborar o revisar nóminas", "b": "Redactar o revisar un contrato", "c": "Calcular finiquito o liquidación", "d": "Regularización de atrasos o diferencias salariales"},
            {"a": "Urgente (esta semana)", "b": "Sin prisa (en 2-3 semanas)"},
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
        "options": [
            {"a": "Alta de trabajador en empresa", "b": "Baja de trabajador en empresa", "c": "Alta como autónomo (RETA)", "d": "Baja como autónomo (RETA)", "e": "Variación de datos o jornada"},
            {"a": "Urgente (hoy o mañana)", "b": "Esta semana", "c": "Sin prisa"},
            {"a": "Sí, tengo todo", "b": "No, necesito saber qué documentos hacen falta"},
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
        "options": [
            {"a": "Desempleo (paro)", "b": "Incapacidad temporal (baja médica)", "c": "Jubilación o prejubilación", "d": "Maternidad / paternidad / excedencia", "e": "Otra (viudedad, orfandad, ingreso mínimo vital...)"},
            {"a": "Trabajador por cuenta ajena", "b": "Autónomo/a"},
            {"a": "No, quiero empezar desde cero", "b": "Sí, tengo una en trámite y tengo dudas"},
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
        "options": [
            {"a": "He recibido una visita de inspección", "b": "Me han llegado requerimientos o propuesta de sanción", "c": "Quiero interponer una denuncia", "d": "Consulta preventiva (quiero saber si cumplo la normativa)"},
            {"a": "Sí, tengo plazo en menos de 7 días", "b": "No, es una consulta sin urgencia inmediata"},
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
        "options": [
            {"a": "Despido o extinción de contrato", "b": "Modificación de condiciones de trabajo", "c": "Convenio colectivo aplicable", "d": "Reclamación de salarios", "e": "Otra consulta laboral"},
            {"a": "Empresa o empleador", "b": "Trabajador/a"},
        ],
        "closing": (
            "✅ Anotado. Dame tu *nombre* y un *email o teléfono* "
            "y te atendemos lo antes posible."
        ),
    },
}

# ── FLUJOS JURÍDICOS ──────────────────────────────────────────────────

FLOWS2 = {
    "1": {
        "name": "Asesoramiento Fiscal",
        "image": "fiscal.png",
        "pdf": None,
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
        "pdf": "asesoramiento_laboral_v3.pdf",
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
        "pdf": "derecho_circulacion_v3.pdf",
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
        "pdf": "derecho_civil_v3.pdf",
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
        "pdf": "derecho_deportivo_v3.pdf",
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
        "pdf": "derecho_extranjeria_v3.pdf",
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
        "pdf": "derecho_laboral_v3.pdf",
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
        "pdf": "derecho_mercantil_v3.pdf",
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
        "pdf": "derecho_urbanismo_v3.pdf",
        "options": (
            "A) Planeamiento Urbanístico\n"
            "B) Expropiaciones\n"
            "C) Expedientes\n"
            "D) Licencias\n"
            "E) Disciplina Urbanística"
        ),
    },
}

# ── MENSAJES ──────────────────────────────────────────────────────────

WELCOME_MESSAGE = (
    f"👋 ¡Hola! Soy el asistente de *{BUSINESS_NAME}*.\n\n"
    "¿En qué área necesitas ayuda?\n\n"
    "1️⃣ Asesoría Laboral y Seguridad Social\n"
    "2️⃣ Servicios Jurídicos"
)

MENU_LABORAL = (
    "¿En qué podemos ayudarte?\n\n"
    "1️⃣ Nóminas y Contratos\n"
    "2️⃣ Altas y Bajas en Seguridad Social\n"
    "3️⃣ Prestaciones y Subsidios\n"
    "4️⃣ Inspección de Trabajo\n"
    "5️⃣ Asesoría Laboral General\n"
    "6️⃣ Hablar con el asesor\n"
    "7️⃣ Solicitar una llamada"
)

MENU_JURIDICO = (
    "¿En qué área jurídica podemos ayudarte?\n\n"
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

TIMEOUT_REMINDER = (
    "¿Sigues ahí? 😊 Puedes continuar cuando quieras "
    "o escribe *MENU* para volver al inicio."
)

INVALID_OPTION_MAIN = (
    "No reconozco esa opción. Por favor elige:\n\n"
    "1️⃣ Asesoría Laboral y Seguridad Social\n"
    "2️⃣ Servicios Jurídicos\n\n"
    "O escribe *MENU* para volver aquí."
)

INVALID_OPTION_LABORAL = (
    "No reconozco esa opción. Por favor elige entre:\n\n"
    "1️⃣ Nóminas y Contratos\n"
    "2️⃣ Altas y Bajas en Seguridad Social\n"
    "3️⃣ Prestaciones y Subsidios\n"
    "4️⃣ Inspección de Trabajo\n"
    "5️⃣ Asesoría Laboral General\n"
    "6️⃣ Hablar con el asesor\n"
    "7️⃣ Solicitar una llamada\n\n"
    "O escribe *MENU* para volver al inicio."
)

INVALID_OPTION_JURIDICO = (
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
    "O escribe *MENU* para volver al inicio."
)


# ── UTILIDADES ────────────────────────────────────────────────────────

def send_whatsapp_message(to: str, text: str) -> None:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
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


def send_whatsapp_image(to: str, image_filename: str, caption: str = "") -> None:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
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


def send_whatsapp_document(to: str, pdf_filename: str, caption: str = "") -> None:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    doc_url = f"{BASE_URL}/static/servicios/{pdf_filename}"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {"link": doc_url, "caption": caption, "filename": pdf_filename},
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending document to {to}: {e}")


def _send_email_thread(subject: str, body: str) -> None:
    if not RESEND_API_KEY:
        print("RESEND_API_KEY no configurada — email no enviado")
        return
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": EMAIL_FROM,
                "to": [ASESOR_EMAIL],
                "subject": subject,
                "text": body,
            },
            timeout=15,
        )
        if response.status_code in (200, 201):
            print(f"Email enviado a {ASESOR_EMAIL}: {subject}")
        else:
            print(f"Error Resend {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error enviando email: {e}")


def send_email(subject: str, body: str) -> None:
    threading.Thread(target=_send_email_thread, args=(subject, body), daemon=True).start()


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


def notify_asesor_juridico(area: str, subopcion: str, contact_info: str, user_phone: str) -> None:
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
        "step": "main_menu",  # main_menu → laboral_menu / juridico_menu → ...
        "bot": None,          # "laboral" o "juridico"
        "service_key": None,
        "q_index": 0,
        "answers": [],
        "area_key": None,
        "subopcion": None,
        "last_activity": datetime.now(),
        "timeout_sent": False,
    }
    user_state[user_id] = state
    return state


def get_state(user_id: str) -> dict:
    if user_id not in user_state:
        return init_state(user_id)
    return user_state[user_id]


def is_menu_keyword(text: str) -> bool:
    return text.strip().lower() in {
        "menu", "menú", "inicio", "start",
        "hola", "hi", "hello", "buenas",
        "buenos días", "buenas tardes", "hey",
    }


# ── LÓGICA UNIFICADA ──────────────────────────────────────────────────

def handle_message(user_id: str, text: str) -> None:
    text_clean = text.strip()
    state = get_state(user_id)
    state["last_activity"] = datetime.now()
    state["timeout_sent"] = False

    # Cualquier keyword de menú vuelve al inicio
    if is_menu_keyword(text_clean):
        init_state(user_id)
        send_whatsapp_message(user_id, WELCOME_MESSAGE)
        return

    step = state["step"]

    # ── MENÚ PRINCIPAL: elegir Laboral o Jurídico ─────────────────────
    if step == "main_menu":
        if text_clean == "1":
            state["bot"] = "laboral"
            state["step"] = "laboral_menu"
            send_whatsapp_message(user_id, MENU_LABORAL)

        elif text_clean == "2":
            state["bot"] = "juridico"
            state["step"] = "juridico_menu"
            send_whatsapp_message(user_id, MENU_JURIDICO)

        else:
            send_whatsapp_message(user_id, INVALID_OPTION_MAIN)

    # ── RAMA LABORAL ──────────────────────────────────────────────────
    elif step == "laboral_menu":
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
            send_whatsapp_message(user_id, INVALID_OPTION_LABORAL)

    elif step == "flow_q":
        flow = FLOWS[state["service_key"]]
        q_opts = flow.get("options", [])
        opt_map = q_opts[state["q_index"]] if state["q_index"] < len(q_opts) else {}
        resolved = opt_map.get(text_clean.lower(), text_clean)
        state["answers"].append(resolved)
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

    # ── RAMA JURÍDICA ─────────────────────────────────────────────────
    elif step == "juridico_menu":
        key = text_clean
        if key in FLOWS2:
            flow = FLOWS2[key]
            state["step"] = "flow2_sub"
            state["area_key"] = key
            send_whatsapp_message(
                user_id,
                f"Estas son las áreas de *{flow['name']}* en las que podemos ayudarte:\n\n"
                f"{flow['options']}\n\n"
                "¿Cuál es tu caso?",
            )
        else:
            send_whatsapp_message(user_id, INVALID_OPTION_JURIDICO)

    elif step == "flow2_sub":
        flow = FLOWS2[state["area_key"]]
        state["subopcion"] = f"{text_clean.upper()} — {flow['name']}"
        state["step"] = "flow2_contact"
        send_whatsapp_message(
            user_id,
            "✅ Entendido.\n\n"
            "Para que nuestro asesor se ponga en contacto contigo, "
            "dinos tu *nombre completo* y un *teléfono o email*.",
        )

    elif step == "flow2_contact":
        flow = FLOWS2[state["area_key"]]
        notify_asesor_juridico(flow["name"], state["subopcion"], text_clean, user_id)
        send_whatsapp_message(
            user_id,
            "✅ ¡Perfecto! Hemos recibido tu consulta.\n\n"
            "Nuestro asesor se pondrá en contacto contigo en menos de 24 horas. 😊",
        )
        # Enviar solo la imagen del área solicitada
        send_whatsapp_message(
            user_id,
            "―――――――――――――――――――\n"
            "🗂️ Te dejamos información ampliada del área que has solicitado. Gracias",
        )
        send_whatsapp_image(user_id, flow["image"], caption=flow["name"])
        send_whatsapp_message(
            user_id,
            "Si necesitas algo más escribe *MENU*.",
        )
        init_state(user_id)


# ── TIMEOUT ───────────────────────────────────────────────────────────

def timeout_checker() -> None:
    while True:
        time.sleep(60)
        now = datetime.now()
        for user_id, state in list(user_state.items()):
            if state["step"] == "main_menu" or state.get("timeout_sent"):
                continue
            elapsed = (now - state["last_activity"]).total_seconds() / 60
            if elapsed >= TIMEOUT_MINUTES:
                send_whatsapp_message(user_id, TIMEOUT_REMINDER)
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

        if message_type != "text":
            send_whatsapp_message(
                from_number,
                "Solo proceso texto por ahora 😊 Escribe *MENU* para ver las opciones.",
            )
            return jsonify({"status": "ok"}), 200

        user_text = message["text"]["body"]

        if from_number not in user_state:
            init_state(from_number)
            send_whatsapp_message(from_number, WELCOME_MESSAGE)
            return jsonify({"status": "ok"}), 200

        handle_message(from_number, user_text)

    except (KeyError, IndexError) as e:
        print(f"Webhook parse error: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running", "bot": f"{BUSINESS_NAME} WhatsApp Bot v2"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
