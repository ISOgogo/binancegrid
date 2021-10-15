import logging, threading, os, time , sys, json
from binance import Client
from decimal import *
from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager


def argument_converter(fn):
    def wrapper(symbol, step, unit, grids, api, secret):
        return fn(symbol, float(step), float(unit), int(grids), api ,secret)
    return wrapper

@argument_converter
def bot(symbol, step, unit, grids, api, secret):
    
    client = Client(api, secret)
    binance_com_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.com")
    binance_com_websocket_api_manager.create_stream('arr', '!userData', api_key=api, api_secret=secret)
    logging.basicConfig(level=logging.INFO,
                    filename=os.path.basename(__file__) + '.log',
                    format="{asctime} [{levelname:8}] {process} {thread} {module}: {message}",
                    style="{")
    
    symbol = symbol.upper() + "USDT"
    ###############################    Helper Functions   ############################################## 
    def make_order(side, price, unit):
        result = None
        c = 0
        while not result and c<10:
            c+=1
            try:
                result = client.create_order(symbol = symbol, side=side, 
        type=Client.ORDER_TYPE_LIMIT, quantity=unit, price = price, timeInForce=Client.TIME_IN_FORCE_GTC)
            except Exception as e:
                print(e)
                time.sleep(0.1)
                pass

        print(f"ORDER OPENED {result['side']} -> {result['price']}")
        return result

    def bulk_buy():

        buy = client.create_order(symbol = symbol, side=Client.SIDE_BUY, type=Client.ORDER_TYPE_MARKET, quantity=unit*5)
        buy_price = None
        while not buy_price:
            try:
                buy_price=float(buy["fills"][0]["price"])
            except:
                pass

        print(f"\nBULK BUY")
        print(buy)
        for i in range(1,6):
            sell = make_order(Client.SIDE_SELL, Decimal("%.2f" % (buy_price + step*i)), unit)
        return buy_price

    def findmin_openOrders():
        orders = client.get_open_orders(symbol=symbol)
        price = 9999999
        orderId = None
        count = 0
        for order in orders:
            if order["side"] == "BUY":
                count += 1
                if float(order["price"]) < price:
                    price = float(order["price"])
                    orderId = order["orderId"]
        return (orderId, count)

    def delete_buy_orders():
        orders = client.get_open_orders(symbol=symbol)
        for order in orders:
            if order["side"] == "BUY":
                client.cancel_order(symbol=symbol, orderId=order["orderId"])
    
    def initialize():
        print("BOT HAS BEEN STARTED")
        price = bulk_buy()
        for i in range(1, grids+1):
            buy = make_order(Client.SIDE_BUY, Decimal("%.2f" % (price - step*i)), unit)
    
    #################################################################################################  
    delete_buy_orders()
    initialize()

    while True:
        oldest_stream_data_from_stream_buffer = binance_com_websocket_api_manager.pop_stream_data_from_stream_buffer()
        
        if oldest_stream_data_from_stream_buffer:
            stream = json.loads(oldest_stream_data_from_stream_buffer)
            

            if stream["e"] == "executionReport" and stream["o"] == "LIMIT" and stream["s"] == symbol and stream["X"] == "FILLED":
                price = float(stream["p"])
                try:
                    if stream["S"] == "SELL":
                        print(f"\nSELL -> {price}")
                        buy = make_order(Client.SIDE_BUY, Decimal("%.2f" % (price - step)), unit)

                        if findmin_openOrders()[1] > grids:  #eğer gridden fazla buy order var ise en küçüğü iptal et
                                deleted = None
                                for i in range(10):
                                    try:
                                        deleted = client.cancel_order(symbol=symbol, orderId=findmin_openOrders()[0] )
                                    except:
                                        pass
                                    if deleted:
                                        break
                        if float(client.get_asset_balance(asset=symbol[:-4])["locked"]) <= unit:
                            bulk_buy()

                    if stream["S"] == "BUY":
                        print(f"\nBUY -> {price} ")
                        sell = make_order(Client.SIDE_SELL, Decimal("%.2f" % (price + step)), unit )
                            
                        buy = make_order(Client.SIDE_BUY, Decimal("%.2f" % (price - step*grids)) , unit )

                except Exception as e:
                    print(e)
                    time.sleep(60)
                    client = Client(api, secret)
                    continue                    

            if stream["e"] == "error":
                print(stream)

        else:
            time.sleep(0.5)

if __name__ == "__main__":
    a =     sys.argv[1]
    b =     float(sys.argv[2])
    c =     float(sys.argv[3])
    d =     int(sys.argv[4])
    api =   sys.argv[5]
    secret= sys.argv[6]

    bot(a, b, c, d, api, secret)

