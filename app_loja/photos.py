"""Imagen principal normalizada y miniatura; sin nombres ni metadatos del archivo."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 12000000


def validate_photo(upload):
    if upload is None or not upload.filename:
        return None
    raw = upload.read(MAX_UPLOAD+1)
    if len(raw)>MAX_UPLOAD:
        raise ValueError('La foto supera 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ('JPEG','PNG','WEBP') or getattr(source,'n_frames',1)!=1:
                    raise ValueError('Elegí una foto JPEG, PNG o WebP sin animación.')
                if max(source.size)>4096 or source.width*source.height>MAX_PIXELS:
                    raise ValueError('La foto supera 4096 píxeles por lado o 12 megapíxeles.')
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                image = ImageOps.exif_transpose(source)
                mode = 'RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB'
                image = image.convert(mode)
                # Una imagen nueva descarta EXIF, GPS, perfiles y comentarios heredados.
                clean = Image.new(mode,image.size)
                clean.paste(image)
                fmt = 'PNG' if mode=='RGBA' else 'JPEG'
                def encode(value):
                    output = BytesIO()
                    value.save(output,format=fmt,**({'quality':90} if fmt=='JPEG' else {}))
                    return output.getvalue()
                principal = encode(clean)
                thumb = clean.copy()
                thumb.thumbnail((240,240),Image.Resampling.LANCZOS)
                miniature = encode(thumb)
                if len(principal)>8*1024*1024:
                    raise ValueError('La foto procesada supera el límite de tamaño. Elegí una imagen más pequeña.')
                return {'imagem':principal,'miniatura':miniature,'mime':'image/png' if fmt=='PNG' else 'image/jpeg',
                    'largura':clean.width,'altura':clean.height}
    except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('No pudimos leer la foto. Elegí una imagen JPEG, PNG o WebP válida.') from None
