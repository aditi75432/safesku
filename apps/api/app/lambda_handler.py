from mangum import Mangum

from app.demo_app import app

handler = Mangum(app, lifespan="off")
