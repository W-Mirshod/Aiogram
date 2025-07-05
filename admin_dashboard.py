
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiosqlite
import datetime
import uvicorn


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return FileResponse("static/dashboard.html")

@app.get("/dashboard-data", response_class=JSONResponse)
async def dashboard_data():
    async with aiosqlite.connect("bot.db") as db:
        users = await db.execute("SELECT user_id, username, language FROM users")
        users = await users.fetchall()
        user_data = []
        for user in users:
            user_id, username, language = user
            joined_cur = await db.execute("SELECT MIN(created_at) FROM queries WHERE user_id = ?", (user_id,))
            joined = await joined_cur.fetchone()
            joined = joined[0] if joined and joined[0] else "-"
            queries_cur = await db.execute("SELECT query, created_at FROM queries WHERE user_id = ? ORDER BY created_at", (user_id,))
            queries = await queries_cur.fetchall()
            now = datetime.datetime.utcnow()
            one_minute_ago = (now - datetime.timedelta(minutes=1)).isoformat()
            limit_cur = await db.execute(
                "SELECT COUNT(*) FROM queries WHERE user_id = ? AND created_at >= ?",
                (user_id, one_minute_ago)
            )
            limit_count = (await limit_cur.fetchone())[0]
            user_data.append({
                "user_id": user_id,
                "username": username,
                "language": language,
                "joined": joined,
                "queries": queries,
                "limit_count": limit_count
            })
    return user_data

if __name__ == "__main__":
    uvicorn.run("admin_dashboard:app", host="0.0.0.0", port=8000, reload=True)
