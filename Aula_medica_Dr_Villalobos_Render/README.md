# Aula médica · Dr. Villalobos

Prototipo funcional y escalable de plataforma docente.

## Qué incluye
- Diseño azul marino, rojo y blanco.
- Fotografía quirúrgica del Dr. Villalobos como perfil.
- Imagen de embarazada en portada.
- Autoría completa.
- QR de Calculadora de Hemorragia Obstétrica.
- QR de MEOWS.
- QR de Ruta Clínica Interactiva.
- Promoción/QR visual del libro.
- Cursos y clases almacenados en SQLite.
- Panel de administrador protegido por contraseña.
- Carga de PPTX, PDF, video e imágenes.
- Modo expositor a pantalla completa.
- Alumnos en modo lectura.
- Exportación de estructura y datos en JSON.
- Diseño adaptable a celular, tableta, laptop y proyector.

## Ejecutar en Windows / macOS / Linux
1. Instalar Python 3.11 o superior.
2. Abrir una terminal dentro de esta carpeta.
3. Instalar dependencias:
   `pip install -r requirements.txt`
4. Cambiar la contraseña de administrador:
   - Windows PowerShell:
     `$env:AULA_ADMIN_PASSWORD="TU_CLAVE_SEGURA"`
   - macOS/Linux:
     `export AULA_ADMIN_PASSWORD="TU_CLAVE_SEGURA"`
5. Ejecutar:
   `uvicorn app:app --host 0.0.0.0 --port 8765`
6. Abrir:
   `http://localhost:8765`

## Uso en clase presencial
Abre la plataforma desde la laptop conectada al proyector. En una clase PDF, imagen o video usa "Modo expositor" para pantalla completa. Si cargas PPTX, el archivo queda disponible para abrirse en PowerPoint conservando animaciones. Para visualizarlo dentro de la web, se recomienda subir además una versión PDF.

## Para convertirla en una plataforma pública real
El siguiente paso es desplegarla en un servidor con dominio propio y HTTPS. Para una versión multiusuario robusta conviene añadir:
- cuentas de alumnos;
- base PostgreSQL;
- almacenamiento de archivos en nube;
- evaluaciones automáticas;
- dashboard por grupo;
- certificados;
- conversión automática PPTX → PDF/imágenes;
- respaldo y auditoría.

## Seguridad
La contraseña incluida por defecto es únicamente de demostración. Antes de publicarla, define `AULA_ADMIN_PASSWORD` con una clave segura.
