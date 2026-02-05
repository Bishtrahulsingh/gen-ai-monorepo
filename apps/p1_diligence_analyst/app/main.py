from packages.core.core.app import create_app

app = create_app()
@app.get('/')
async def root():
    return {'message':'welcome to our website'}

