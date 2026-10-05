# AVICO Cloud — Fase 1

Esta rama inicia la evolución del Aula Virtual AVICO hacia AVICO Cloud sin interrumpir el curso de Hemorragia Obstétrica.

## Objetivos de esta fase

- Conservar el Aula de Hemorragia Obstétrica y la identidad visual actual.
- Separar el almacenamiento audiovisual del servidor web.
- Preparar reproducción por streaming privado mediante un proveedor externo.
- Registrar progreso por alumno, curso y lección.
- Mantener compatibilidad con las lecciones y archivos actuales durante la migración.

## Arquitectura objetivo

Navegador → AVICO Cloud (FastAPI/Render) → autenticación y autorización → proveedor de streaming.

La base de datos guarda metadatos y progreso; los archivos de video no deben residir en el disco del servidor de aplicación.

## Variables previstas

- AVICO_STREAM_PROVIDER
- AVICO_STREAM_ACCOUNT_ID
- AVICO_STREAM_API_TOKEN
- AVICO_STREAM_SIGNING_KEY

Las credenciales nunca deben almacenarse en GitHub.

## Migración

1. Añadir modelo de progreso y metadatos de streaming.
2. Incorporar endpoints autenticados para reproducción y progreso.
3. Conectar el reproductor del Aula.
4. Migrar cada video de Hemorragia Obstétrica sin cambiar el contenido del curso.
5. Validar reproducción móvil y escritorio.
6. Cuando todo esté validado, retirar el uso de MP4 locales para esas lecciones.

No se elimina la infraestructura actual hasta verificar la migración.


## Piloto previo a Hemorragia Obstétrica

Antes de migrar el curso de Hemorragia Obstétrica, AVICO Cloud se validará en el Aula AVICO general.

Criterios del piloto:
- usar una sola clase/video de prueba;
- mantener intactas las ponencias de Hemorragia Obstétrica;
- comprobar inicio de sesión e inscripción activa;
- comprobar reproducción protegida en escritorio y móvil;
- guardar avance y reanudar desde la última posición;
- verificar finalización y persistencia del progreso;
- conservar el archivo local como respaldo;
- no migrar Hemorragia hasta completar satisfactoriamente estas pruebas.

Rama de validación: `avico-cloud-pilot`.
