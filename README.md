# Aviso automático del blog de inglés

Vigila https://riosginerlisbon.blogspot.com/ y te manda una notificación al
móvil en cuanto aparece una entrada nueva que mencione "1º Bach".

## 1. Crea tu bot de Telegram

1. En Telegram, busca el usuario **@BotFather** (es el bot oficial para crear bots).
2. Escríbele `/newbot` y sigue las instrucciones: te pedirá un nombre para
   mostrar y un "username" que debe terminar en `bot` (ej. `AvisoBlogInglesBot`).
3. Al terminar, BotFather te da un **token**, algo como:
   `123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`
   Guárdalo, lo necesitarás en el paso 3.
4. Ahora busca tu bot por el username que le pusiste y pulsa **Iniciar** (o
   escríbele cualquier mensaje, ej. "hola"). Esto es necesario para que el bot
   pueda escribirte a ti luego.
5. Para saber tu **chat_id**, abre en el navegador (sustituyendo el token):
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   Verás un JSON; busca `"chat":{"id":XXXXXXXXX,...}` — ese número es tu
   `chat_id`. Si no aparece nada, asegúrate de haberle escrito al bot primero
   y recarga la página.

## 2. Crea el repositorio en GitHub

1. Ve a https://github.com/new
2. Ponle un nombre (ej. `blog-watcher`) y márcalo como **público** (así los
   minutos de GitHub Actions son gratis e ilimitados). No hace falta que sea
   privado, el contenido no es sensible.
3. Sube todos estos archivos (arrastra la carpeta descomprimida en la web de
   GitHub, o usa `git`).

## 3. Configura los secretos en GitHub

En tu repositorio: **Settings → Secrets and variables → Actions → New
repository secret**. Crea dos secretos:

1. Nombre: `TELEGRAM_BOT_TOKEN` → Valor: el token que te dio BotFather.
2. Nombre: `TELEGRAM_CHAT_ID` → Valor: el número que sacaste de `getUpdates`.

## 4. Activa las Actions

1. Ve a la pestaña **Actions** de tu repositorio.
2. Si te pide habilitarlas, acéptalo.
3. Entra en el workflow "Revisar blog de inglés" y pulsa **Run workflow** para
   probarlo manualmente una vez.
4. La primera ejecución NO manda ningún aviso (solo memoriza qué entradas ya
   existen para no avisarte de cosas viejas). A partir de la segunda vez que
   se ejecute, si hay algo nuevo relevante, te llegará la notificación.

A partir de aquí funciona solo: cada 5 minutos entre las 16:00 y las 18:00
hora de Portugal (con un pequeño margen para cubrir el cambio de hora
invierno/verano).

## Ajustes que puedes querer cambiar

- **Qué se considera relevante**: en `check_blog.py`, la variable
  `RELEVANT_PATTERN` decide qué entradas se consideran para ti. Ahora mismo
  busca la combinación "1" + "Bach" en cualquier forma: "1º Bach",
  "1 Bachillerato A", "1 Bachillerato B", "1bach"... no hace falta escribir
  cada variante a mano, ni las letras de cada clase — cualquier cosa que
  empiece por "1 Bach..." cuela, venga como venga escrita. Si algún día
  quieres que te avise de TODO sin filtrar, deja
  `RELEVANT_PATTERN = re.compile(r".")`.
- **Horario de revisión**: en `.github/workflows/check_blog.yml`, las líneas
  `cron` controlan cuándo se revisa. Ahora mismo es la franja 15:00-18:00 UTC,
  que equivale a las 16:00-18:00 hora portuguesa (con margen para el cambio
  de hora).
- **Privacidad**: el token del bot y tu chat_id están guardados como
  "Secrets" de GitHub, que no son visibles ni siquiera para ti una vez
  guardados (solo se puede sobrescribirlos), y nunca aparecen en los logs de
  las Actions. Aun así, no compartas el token con nadie: quien lo tenga
  podría usar el bot para escribirte.

## Cómo funciona por dentro

- El blog es de Blogger, así que tiene un feed Atom automático en
  `/feeds/posts/default`. El script lee ese feed en vez de "leer" la web
  directamente, es más fiable.
- `state.json` guarda qué entradas ya se han visto, para no repetir avisos.
  GitHub Actions lo actualiza y lo sube al repo solo, después de cada
  ejecución.
