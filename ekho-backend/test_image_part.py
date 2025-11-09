from google.genai import types
img = types.Image()
print(dir(img))
try:
    print(img.__fields__)
except:
    pass
try:
    print(img.model_fields)
except:
    pass
