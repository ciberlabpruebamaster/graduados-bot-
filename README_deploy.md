# Bot WhatsApp — Asesoría Graduados Sociales

Bot de WhatsApp para despachos de Graduados Sociales. Captura leads laborales con flujos guiados y notifica al asesor en tiempo real.

---

## Stack

- Python 3 + Flask
- Meta WhatsApp Business API
- Despliegue: Railway (recomendado) o cualquier PaaS con soporte Python

---

## Flujos disponibles

| Opción | Servicio |
|--------|----------|
| 1 | Nóminas y Contratos |
| 2 | Altas y Bajas en Seguridad Social |
| 3 | Prestaciones y Subsidios |
| 4 | Inspección de Trabajo |
| 5 | Asesoría Laboral General |
| 6 | Hablar con el asesor |
| 7 | Solicitar una llamada |

---

## Variables de entorno necesarias

| Variable | Descripción |
|----------|-------------|
| `BUSINESS_NAME` | Nombre del despacho (aparece en los mensajes) |
| `WHATSAPP_TOKEN` | Token de acceso de Meta (permanente) |
| `PHONE_NUMBER_ID` | ID del número de WhatsApp Business |
| `ASESOR_PHONE` | Teléfono del asesor que recibe leads (ej: 34666123456) |
| `VERIFY_TOKEN` | Token para verificar el webhook (ej: graduados2024) |
| `APP_SECRET` | Secreto de la app Meta (opcional, mejora seguridad) |
| `PORT` | Puerto (Railway lo asigna solo) |

---

## Despliegue en Railway

1. Crea un nuevo proyecto en [railway.app](https://railway.app)
2. Conecta este repositorio de GitHub
3. Añade las variables de entorno en el panel de Railway
4. Railway detecta el `Procfile` y despliega automáticamente
5. Copia la URL pública generada (ej: `https://tu-app.up.railway.app`)

---

## Configuración del Webhook en Meta

1. Ve a [developers.facebook.com](https://developers.facebook.com) → tu app
2. En **WhatsApp > Configuración**, añade el webhook:
   - URL: `https://tu-app.up.railway.app/webhook`
   - Token de verificación: el valor de `VERIFY_TOKEN`
3. Suscríbete al evento `messages`

---

## Diferencias respecto al bot de Nebulosa Digital

| Aspecto | Nebulosa Digital | Graduados Sociales |
|---------|------------------|--------------------|
| Nicho | Marketing digital | Asesoría laboral |
| Servicios | Diseño web, imagen, vídeo, etc. | Nóminas, TGSS, prestaciones, inspección |
| Horario | L-V 9:00-19:00h | L-V 9:00-18:00h |
| Lead receiver | Ellena (hardcoded) | `ASESOR_PHONE` (variable de entorno) |
| Nombre negocio | Hardcoded | `BUSINESS_NAME` (variable de entorno) |
| WhatsApp bot | +34 601 28 20 82 | Tu número nuevo (configurar en Meta) |

---

## Personalización rápida

- **Nombre del despacho**: cambia `BUSINESS_NAME` en Railway
- **Número receptor de leads**: cambia `ASESOR_PHONE` en Railway
- **Horario de atención**: edita `is_business_hours()` en `main.py`
- **Añadir/quitar servicios**: modifica el diccionario `FLOWS` en `main.py`
