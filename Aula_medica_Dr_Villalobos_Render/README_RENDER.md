# Aula médica · Dr. Villalobos — lista para Render

Esta versión está preparada para publicarse desde un repositorio GitHub usando Render.

## Incluye
- FastAPI + Uvicorn.
- Interfaz responsive para celular, tableta, laptop y proyector.
- Panel privado de administrador.
- Carga de PPTX, PDF, video e imágenes.
- Modo expositor.
- SQLite y archivos subidos dentro de un disco persistente de Render.
- `render.yaml` para despliegue por Blueprint.
- Health check `/health`.

## Publicación
1. Crea en GitHub un repositorio llamado, por ejemplo, `aula-medica-dr-villalobos`.
2. Sube todo el contenido de esta carpeta.
3. En Render selecciona `New` → `Blueprint`.
4. Conecta GitHub y selecciona el repositorio.
5. Render leerá automáticamente `render.yaml`.
6. Confirma la creación del servicio.

Render generará una URL pública `onrender.com`.

## Persistencia
El código permanece en GitHub. Las clases, la base de datos SQLite y los archivos cargados desde el panel se guardan en `/var/data`, que es el disco persistente configurado en `render.yaml`.

## Administrador
`AULA_ADMIN_PASSWORD` se genera automáticamente en Render. Puedes sustituirla por tu propia contraseña desde Environment.

## Escalabilidad
Para una segunda etapa con muchos alumnos y grupos se recomienda migrar SQLite a PostgreSQL y los archivos a almacenamiento tipo S3/R2, manteniendo la misma interfaz.
