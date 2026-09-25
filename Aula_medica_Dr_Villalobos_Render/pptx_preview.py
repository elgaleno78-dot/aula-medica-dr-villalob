"""Private slide previews. The original PPTX never goes to student browsers."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

FONT_PATH="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

@lru_cache(maxsize=8)
def presentation(path, mtime):
    return Presentation(path)

def slide_count(path):
    p=Path(path)
    return len(presentation(str(p),p.stat().st_mtime_ns).slides)

def _font(size,bold=False):
    try: return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH,max(10,int(size)))
    except OSError: return ImageFont.load_default()

def _color(value,default):
    try:
        if value and value.type and value.rgb: return tuple(value.rgb)
    except (AttributeError,ValueError,TypeError): pass
    return default

def render_slide(path, number, width=1280):
    p=Path(path); prs=presentation(str(p),p.stat().st_mtime_ns)
    if number<1 or number>len(prs.slides): raise IndexError("Slide out of range")
    scale=width/prs.slide_width; height=round(prs.slide_height*scale)
    canvas=Image.new("RGB",(width,height),"white")
    draw=ImageDraw.Draw(canvas)
    slide=prs.slides[number-1]
    try:
        fill=slide.background.fill
        if fill.type and fill.fore_color.type:
            canvas.paste(_color(fill.fore_color,(255,255,255)),(0,0,width,height))
    except (AttributeError,ValueError,TypeError): pass
    for shape in slide.shapes:
        x=round(shape.left*scale); y=round(shape.top*scale)
        w=max(1,round(shape.width*scale)); h=max(1,round(shape.height*scale))
        if shape.shape_type==MSO_SHAPE_TYPE.PICTURE:
            try:
                im=Image.open(BytesIO(shape.image.blob)).convert("RGBA")
                im.thumbnail((w,h),Image.Resampling.LANCZOS)
                canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2),im)
            except Exception: pass
        else:
            try:
                fill=shape.fill
                if fill.type:
                    c=_color(fill.fore_color,None)
                    if c: draw.rectangle((x,y,x+w,y+h),fill=c)
            except (AttributeError,ValueError,TypeError): pass
        if not shape.has_text_frame: continue
        frame=shape.text_frame
        tx=x+max(3,round(frame.margin_left*scale))
        ty=y+max(2,round(frame.margin_top*scale))
        maxx=x+w-max(3,round(frame.margin_right*scale))
        for paragraph in frame.paragraphs:
            runs=paragraph.runs
            if not runs:
                ty+=16; continue
            for run in runs:
                size=(run.font.size.pt if run.font.size else 18)*scale*12700/914400
                # PowerPoint font points to screen pixels at slide scale.
                size=(run.font.size.pt if run.font.size else 18)*width/(prs.slide_width/914400*72)
                font=_font(size,bool(run.font.bold))
                color=_color(run.font.color,(25,40,55))
                for word in run.text.replace("\\v","\\n").split(" "):
                    for j,line in enumerate(word.split("\\n")):
                        chunk=line+(" " if j==len(word.split("\\n"))-1 else "")
                        if tx+draw.textlength(chunk,font=font)>maxx and tx>x+4:
                            tx=x+max(3,round(frame.margin_left*scale));ty+=round(size*1.3)
                        if ty>y+h: break
                        draw.text((tx,ty),chunk,font=font,fill=color)
                        tx+=round(draw.textlength(chunk,font=font))
                        if j<len(word.split("\\n"))-1:
                            tx=x+4;ty+=round(size*1.3)
            tx=x+max(3,round(frame.margin_left*scale))
            ty+=round(size*1.35)
    output=BytesIO();canvas.save(output,format="JPEG",quality=85,optimize=True)
    return output.getvalue()
