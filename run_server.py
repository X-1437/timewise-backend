import uvicorn
import os
os.chdir(r"D:\workspace\data_analysis\timewise-backend")
uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
