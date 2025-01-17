from telegram import Update, ReplyKeyboardMarkup, InputFile
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from io import BytesIO
from telegram.ext import ContextTypes
import logging
from bi_api.data_extraction import get_historical_data
from indicators.technical_indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_stochastic

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class IndicatorHandler:
    @staticmethod
    async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Вибір пари для індикаторів."""
        await update.callback_query.edit_message_text("Виберіть пару для аналізу.")
        # Додати логіку для вибору пари (можливо, через інші кнопки або вибір користувача).

    @staticmethod
    async def handle_tech_indicators_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        from main import START_ROUTES

        """Обробка вибору індикаторів."""
        query = update.callback_query
        await query.answer()

        if query.data == str(5):  # BACK_TO_START
            await query.edit_message_text("Повернення до головного меню.")
            return START_ROUTES  # Повернення до головного меню

        elif query.data == str(3):  # CHOOSE_INDICATORS
            await IndicatorHandler.select_pair(update, context)
            await IndicatorHandler.select_indicators(update, context)

        elif query.data == str(4):  # ALL_INDICATORS
            context.user_data['selected_indicators'] = ["RSI", "MACD", "Bollinger Bands", "Stochastic"]
            await query.edit_message_text(f"Обрано всі індикатори: {', '.join(context.user_data['selected_indicators'])}")
            await IndicatorHandler.show_info(update, context)

        return 1  # Залишаємося у тому ж стані

    @staticmethod
    async def select_indicators(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показати клавіатуру для вибору технічних індикаторів після вибору пари."""
        indicators = [["RSI", "MACD"], ["Bollinger Bands", "Stochastic"], ["Усі"]]
        keyboard = ReplyKeyboardMarkup(indicators, one_time_keyboard=True)

        if update.callback_query:
            await update.callback_query.message.reply_text("Оберіть технічні індикатори:", reply_markup=keyboard)

    @staticmethod
    async def handle_indicator_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обробка вибору індикаторів та виконання аналізу."""
        selected_indicators = update.message.text if update.message else update.callback_query.data

        if selected_indicators == "Усі":
            context.user_data['selected_indicators'] = ["RSI", "MACD", "Bollinger Bands", "Stochastic"]
        else:
            context.user_data['selected_indicators'] = [selected_indicators]

        response_text = f"Індикатори: {', '.join(context.user_data['selected_indicators'])}"

        if update.message:
            await update.message.reply_text(response_text)
        elif update.callback_query:
            await update.callback_query.message.reply_text(response_text)

        await IndicatorHandler.show_info(update, context)
        return 1  # Повертаємося до вибору дій після виконання аналізу

    @staticmethod
    async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Відображення свічкового графіка з технічними індикаторами та відправка PNG картинки"""
        symbol = context.user_data.get('selected_pair')
        selected_indicators = context.user_data.get('selected_indicators', [])

        try:
            # Отримуємо історичні дані
            data = get_historical_data(symbol, "1d")
            logger.info(f"Fetched data: {data.head()}")

            # Перевірка наявності необхідних колонок
            if 'timestamp' not in data.columns or 'close' not in data.columns:
                raise ValueError("Очікувані колонки 'timestamp' і 'close' відсутні в даних.")

            # Конвертуємо timestamp в формат дати
            data['date'] = pd.to_datetime(data['timestamp'], unit='ms')
            data.set_index('date', inplace=True)

            # Конвертуємо дані у числовий формат
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

            # Видаляємо рядки з пропущеними значеннями, якщо такі є
            data.dropna(subset=numeric_columns, inplace=True)

            # Створення свічкового графіка
            ohlc_data = data[['open', 'high', 'low', 'close', 'volume']]

            # Налаштування індикаторів
            add_plots = []
            if "RSI" in selected_indicators:
                rsi = calculate_rsi(data)
                add_plots.append(mpf.make_addplot(rsi, panel=1, color='blue', ylabel='RSI'))

            if "MACD" in selected_indicators:
                macd_line, macd_signal = calculate_macd(data['close'])
                add_plots.append(mpf.make_addplot(macd_line, panel=2, color='orange', ylabel='MACD Line'))
                add_plots.append(mpf.make_addplot(macd_signal, panel=2, color='red', ylabel='MACD Signal'))

            if "Bollinger Bands" in selected_indicators:
                upper_band, lower_band = calculate_bollinger_bands(data)
                add_plots.append(mpf.make_addplot(upper_band, color='green'))
                add_plots.append(mpf.make_addplot(lower_band, color='purple'))

            if "Stochastic" in selected_indicators:
                stoch_k, stoch_d = calculate_stochastic(data)
                add_plots.append(mpf.make_addplot(stoch_k, panel=3, color='cyan', ylabel='Stochastic K'))
                add_plots.append(mpf.make_addplot(stoch_d, panel=3, color='magenta', ylabel='Stochastic D'))

            # Налаштування стилю графіка
            style = mpf.make_mpf_style(base_mpf_style='charles', facecolor='white')

            # Створення графіка
            fig, axlist = mpf.plot(
                ohlc_data,
                type='candle',  # Свічковий графік
                volume=True,    # Додаємо об'єм
                addplot=add_plots,  # Додаємо технічні індикатори
                style=style,    # Стиль графіка
                returnfig=True,
                figsize=(60, 30)  # Розмір графіка
            )

            logger.info(f"Fig with fig_size: {fig}")
            # Збереження графіка в буфер
            image_stream = BytesIO()
            fig.savefig(image_stream, format='png')
            image_stream.seek(0)  # Переміщаємо курсор на початок
            plt.close(fig)

            # Відправка графіка в Telegram через callback_query
            await update.callback_query.message.reply_photo(photo=InputFile(image_stream, filename='chart.png'))

        except Exception as e:
            logger.error(f"Помилка при отриманні даних: {e}")
            await update.callback_query.message.reply_text('Виникла помилка при отриманні даних.')

