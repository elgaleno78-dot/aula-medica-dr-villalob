# AVICO® Aula Educación — carpeta de ponencias

Carpeta exclusiva: https://drive.google.com/drive/folders/18jrR5TnL-Qxh5ktar2r_mg8dfIi0KYeW

ID: `18jrR5TnL-Qxh5ktar2r_mg8dfIi0KYeW`

## Integración existente

El backend ya implementa reproducción autenticada de clases de tipo `drive` mediante `/api/drive/player/{lesson_id}` y `/api/drive/media/{lesson_id}`. Cada clase utiliza en `lessons.filename` el ID del archivo de video, no el ID de la carpeta. La carpeta es el repositorio de archivos, no un curso automático.

## Pasos pendientes

1. Compartir esta carpeta con la cuenta de servicio Google Drive usada por el Aula AVICO principal, con permiso de lector, sin habilitar acceso público.
2. Subir los videos MP4 a la carpeta.
3. Registrar cada video como una ponencia `kind=drive` y su ID de archivo en el curso correspondiente del Aula Educación; no modificar el curso ni la carpeta de Hemorragia.
4. Verificar con una cuenta de alumno la reproducción, controles de acceso y rangos de video.
5. Evitar anunciar sincronización automática: el backend actual asocia IDs individuales de archivos y no indexa automáticamente toda la carpeta.

No se han movido ponencias ni cambiado inscripciones o registros de estudiantes.
