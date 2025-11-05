from app import app

# Vercel requiere que el app sea una función callable
def handler(request):
    return app(request)
