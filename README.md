# 🤖 tradagent — وكيل التداول الذكي (سريع • عملي • متكامل)

نسخة عملية محسّنة من فكرة [ai-trading-agent-gemini](https://github.com/danilobatson/ai-trading-agent-gemini):
نفس خط الأنابيب (7 خطوات: تهيئة → عملات → جلب → تحليل AI → حفظ → ملخص → إتمام)، لكن:

| الأصل | tradagent |
|---|---|
| Next.js + Inngest + Supabase (5 مفاتيح إجبارية، 30-45 ثانية) | Python + SQLite محلي (0 مفاتيح إجبارية، 3-8 ثوانٍ) |
| يتوقف بدون LunarCrush/Gemini مدفوعة | يعمل فوراً بمحرك محلي + Binance/CoinGecko المجانية، ويدعم Gemini/LunarCrush عند توفرها |
| realtime معقد | جلب متوازي + كاش + داشبورد مدمجة بدون اعتماديات |

## 🚀 التشغيل (دقيقتان)

```bash
cd tradagent
pip install -r requirements.txt
cp .env.example .env   # اختياري — يعمل بدونها
python run.py                          # تحليل فوري: BTC,ETH,SOL,BNB,XRP
python cli.py run --symbols BTC,ETH    # عملات مخصصة
python cli.py signals --limit 10       # عرض الإشارات المحفوظة
python cli.py backtest --symbols BTC   # باك تست سريع
python cli.py dashboard --port 8000    # لوحة عربية حية http://localhost:8000
```

## 🧠 كيف يعمل

1. **جلب متوازي** (`data_providers.py`): Binance klines + ticker لكل العملات معاً (ThreadPool) + كاش 5 دقائق + fallback CoinGecko.
2. **مؤشرات**: RSI-14، زخم 48h، تذبذب، تغير 24h + (Galaxy/Sentiment إن وُجد LunarCrush).
3. **AI هجين** (`ai_engine.py`): يستخدم **Gemini 1.5 Flash** إن وُجد `GOOGLE_GEMINI_API_KEY`، وإلا المحرك الكمي المحلي (<1ms، يعمل أوفلاين).
4. **تخزين** (`database.py`): SQLite + WAL + فهارس — نفس جدولَي الأصل (`trading_signals`, `analysis_jobs`).
5. **تنبيهات Discord** تلقائية إن وُجد webhook.

## ⚡ لماذا أسرع؟

- جلب متوازي (8 workers) بدل التسلسلي → ~5x أسرع.
- لا Inngest/Supabase round-trips — كل شيء محلي.
- كاش TTL يمنع إعادة الجلب.
- محرك محلي فوري بدل انتظار Gemini لكل عملة (Gemini اختياري بالتوازي أيضاً).

## ⚠️ إخلاء مسؤولية

ليست نصيحة مالية. الإشارات تعليمية — جرّب `backtest` أولاً ولا تتداول بأموال حقيقية دون فهم المخاطر.
