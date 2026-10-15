//+------------------------------------------------------------------+
//|                                                AgentBridge.mq5 |
//| Writes market state for the Python agent and places its orders. |
//| Every order must arrive with a hard stop. Lot size is clamped   |
//| to the broker minimum, step, and maximum.                       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input string InpSymbols          = "EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,XAUUSD,BTCUSD,ETHUSD";
input ulong  InpMagic            = 20261015;
input int    InpDeviationPoints  = 50;
input int    InpTimerSeconds     = 2;

CTrade   g_trade;
int      g_fillIndex = 2;
string   g_symbols[];

struct IndSet
  {
   string            symbol;
   ENUM_TIMEFRAMES   tf;
   int               macd;
   int               atr;
   int               ema;
   int               rsi;
  };

IndSet g_ind[];

//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING FillByIndex(const int index)
  {
   if(index == 0)
      return(ORDER_FILLING_FOK);
   if(index == 1)
      return(ORDER_FILLING_IOC);
   return(ORDER_FILLING_RETURN);
  }

//+------------------------------------------------------------------+
int StartingFillIndex()
  {
   long exec = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE);
   if(exec == SYMBOL_TRADE_EXECUTION_EXCHANGE)
      return(2);
   long fill = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fill & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return(1);
   if((fill & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return(0);
   return(2);
  }

//+------------------------------------------------------------------+
bool FillRejected()
  {
   return(g_trade.ResultRetcode() == TRADE_RETCODE_INVALID_FILL);
  }

//+------------------------------------------------------------------+
void ApplyFilling(const int index)
  {
   g_trade.SetTypeFilling(FillByIndex(index));
  }

//+------------------------------------------------------------------+
int SplitList(const string text, const ushort sep, string &items[])
  {
   string work = text;
   StringReplace(work, " ", "");
   return(StringSplit(work, sep, items));
  }

//+------------------------------------------------------------------+
void AddTimeframe(const string symbol, const ENUM_TIMEFRAMES tf)
  {
   for(int i = 0; i < ArraySize(g_ind); i++)
      if(g_ind[i].symbol == symbol && g_ind[i].tf == tf)
         return;
   int macd = iMACD(symbol, tf, 12, 26, 9, PRICE_CLOSE);
   int atr = iATR(symbol, tf, 14);
   int ema = iMA(symbol, tf, 200, 0, MODE_EMA, PRICE_CLOSE);
   int rsi = iRSI(symbol, tf, 14, PRICE_CLOSE);
   if(macd == INVALID_HANDLE || atr == INVALID_HANDLE || ema == INVALID_HANDLE || rsi == INVALID_HANDLE)
     {
      if(macd != INVALID_HANDLE) IndicatorRelease(macd);
      if(atr != INVALID_HANDLE) IndicatorRelease(atr);
      if(ema != INVALID_HANDLE) IndicatorRelease(ema);
      if(rsi != INVALID_HANDLE) IndicatorRelease(rsi);
      return;
     }
   int n = ArraySize(g_ind);
   ArrayResize(g_ind, n + 1);
   g_ind[n].symbol = symbol;
   g_ind[n].tf = tf;
   g_ind[n].macd = macd;
   g_ind[n].atr = atr;
   g_ind[n].ema = ema;
   g_ind[n].rsi = rsi;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   SplitList(InpSymbols, ',', g_symbols);
   if(ArraySize(g_symbols) < 1)
      return(INIT_FAILED);
   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      SymbolSelect(g_symbols[i], true);
      AddTimeframe(g_symbols[i], PERIOD_M15);
      AddTimeframe(g_symbols[i], PERIOD_H1);
      AddTimeframe(g_symbols[i], PERIOD_H4);
      AddTimeframe(g_symbols[i], _Period);
     }
   if(ArraySize(g_ind) < 1)
      return(INIT_FAILED);
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_fillIndex = StartingFillIndex();
   ApplyFilling(g_fillIndex);
   EventSetTimer(MathMax(1, InpTimerSeconds));
   Print("AgentBridge ready. Symbols=", ArraySize(g_symbols), " feeds=", ArraySize(g_ind));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < ArraySize(g_ind); i++)
     {
      IndicatorRelease(g_ind[i].macd);
      IndicatorRelease(g_ind[i].atr);
      IndicatorRelease(g_ind[i].ema);
      IndicatorRelease(g_ind[i].rsi);
     }
  }

//+------------------------------------------------------------------+
bool OneValue(const int handle, const int buffer, double &value)
  {
   double data[];
   ArraySetAsSeries(data, true);
   if(CopyBuffer(handle, buffer, 1, 1, data) != 1)
      return(false);
   value = data[0];
   return(true);
  }

//+------------------------------------------------------------------+
void WriteLine(const int handle, const string line)
  {
   FileWriteString(handle, line + "\n");
  }

//+------------------------------------------------------------------+
void WriteAck(const string commandId, const string status, const string detail)
  {
   int handle = FileOpen("agent_ack.txt", FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      handle = FileOpen("agent_ack.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return;
   FileSeek(handle, 0, SEEK_END);
   FileWriteString(handle, commandId + "|" + status + "|" + detail + "\n");
   FileClose(handle);
  }

//+------------------------------------------------------------------+
void WriteState()
  {
   int handle = FileOpen("agent_state.tmp", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return;
   MqlDateTime stamp;
   TimeToStruct(TimeCurrent(), stamp);
   stamp.day = 1;
   stamp.hour = 0;
   stamp.min = 0;
   stamp.sec = 0;
   WriteLine(handle, "CHART|" + EnumToString(_Period));
   WriteLine(handle,
             "ACCOUNT|" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "|" +
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "|" +
             DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + "|" +
             AccountInfoString(ACCOUNT_CURRENCY) + "|" +
             IntegerToString((int)AccountInfoInteger(ACCOUNT_LEVERAGE)));

   for(int i = 0; i < ArraySize(g_ind); i++)
     {
      string symbol = g_ind[i].symbol;
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(bid <= 0.0 || ask < bid || point <= 0.0)
         continue;
      double atr, ema, macd, signal, rsi;
      if(!OneValue(g_ind[i].atr, 0, atr))
         continue;
      if(!OneValue(g_ind[i].ema, 0, ema))
         continue;
      if(!OneValue(g_ind[i].macd, 0, macd))
         continue;
      if(!OneValue(g_ind[i].macd, 1, signal))
         continue;
      if(!OneValue(g_ind[i].rsi, 0, rsi))
         continue;
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double spreadPoints = (ask - bid) / point;
      WriteLine(handle,
                "SYMBOL|" + symbol + "|" + EnumToString(g_ind[i].tf) + "|" +
                DoubleToString(bid, digits) + "|" + DoubleToString(ask, digits) + "|" +
                DoubleToString(point, digits + 1) + "|" + IntegerToString(digits) + "|" +
                DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN), 8) + "|" +
                DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX), 8) + "|" +
                DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP), 8) + "|" +
                DoubleToString(spreadPoints, 1) + "|" +
                DoubleToString(atr, digits) + "|" + DoubleToString(ema, digits) + "|" +
                DoubleToString(macd, 8) + "|" + DoubleToString(signal, 8) + "|" +
                DoubleToString(rsi, 2) + "|" +
                DoubleToString(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE), 8) + "|" +
                DoubleToString(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE), 8));
     }

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      string kind = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL");
      WriteLine(handle,
                "POSITION|" + IntegerToString((long)ticket) + "|" +
                PositionGetString(POSITION_SYMBOL) + "|" + kind + "|" +
                DoubleToString(PositionGetDouble(POSITION_VOLUME), 8) + "|" +
                DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 8) + "|" +
                DoubleToString(PositionGetDouble(POSITION_SL), 8) + "|" +
                DoubleToString(PositionGetDouble(POSITION_TP), 8) + "|" +
                DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + "|" +
                IntegerToString((long)InpMagic));
     }

   if(HistorySelect(StructToTime(stamp), TimeCurrent()))
     {
      for(int i = 0; i < HistoryDealsTotal(); i++)
        {
         ulong deal = HistoryDealGetTicket(i);
         if(deal == 0)
            continue;
         if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
            continue;
         long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
         string entryName = "IN";
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
            entryName = "OUT";
         long dtype = HistoryDealGetInteger(deal, DEAL_TYPE);
         string kind = (dtype == DEAL_TYPE_BUY ? "BUY" : "SELL");
         WriteLine(handle,
                   "DEAL|" + IntegerToString((long)deal) + "|" +
                   IntegerToString((long)HistoryDealGetInteger(deal, DEAL_POSITION_ID)) + "|" +
                   HistoryDealGetString(deal, DEAL_SYMBOL) + "|" + kind + "|" +
                   DoubleToString(HistoryDealGetDouble(deal, DEAL_VOLUME), 8) + "|" +
                   DoubleToString(HistoryDealGetDouble(deal, DEAL_PRICE), 8) + "|" +
                   DoubleToString(HistoryDealGetDouble(deal, DEAL_PROFIT), 2) + "|" +
                   IntegerToString((long)HistoryDealGetInteger(deal, DEAL_TIME)) + "|" +
                   entryName);
        }
     }
   FileClose(handle);
   FileDelete("agent_state.csv");
   FileMove("agent_state.tmp", 0, "agent_state.csv", FILE_REWRITE);
  }

//+------------------------------------------------------------------+
double ClampLots(const string symbol, double lots)
  {
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0)
      return(0.0);
   lots = MathFloor(lots / step) * step;
   if(lots < minLot || lots > maxLot)
     {
      if(lots > maxLot)
         lots = MathFloor(maxLot / step) * step;
      if(lots < minLot)
         return(0.0);
     }
   int digits = 0;
   double probe = step;
   while(digits < 8 && MathAbs(probe - MathRound(probe)) > 0.0000001)
     {
      probe *= 10.0;
      digits++;
     }
   return(NormalizeDouble(lots, digits));
  }

//+------------------------------------------------------------------+
bool SendWithFilling(const bool buy, const string symbol, const double lots, const double price,
                     const double sl, const double tp, const string comment)
  {
   int first = g_fillIndex;
   for(int attempt = 0; attempt < 3; attempt++)
     {
      ApplyFilling(g_fillIndex);
      bool sent = false;
      if(buy)
         sent = g_trade.Buy(lots, symbol, price, sl, tp, comment);
      else
         sent = g_trade.Sell(lots, symbol, price, sl, tp, comment);
      if(sent)
         return(true);
      if(!FillRejected())
         return(false);
      g_fillIndex = (g_fillIndex + 1) % 3;
      if(g_fillIndex == first)
         break;
     }
   return(false);
  }

//+------------------------------------------------------------------+
void ExecuteCommand(const string line)
  {
   string part[];
   int count = StringSplit(line, '|', part);
   if(count < 6)
      return;
   string commandId = part[0];
   string action = part[1];
   string symbol = part[2];
   double lots = ClampLots(symbol, StringToDouble(part[3]));
   double sl = StringToDouble(part[4]);
   double tp = StringToDouble(part[5]);
   string comment = (count > 6 ? part[6] : "agent");
   if(StringLen(comment) > 31)
      comment = StringSubstr(comment, 0, 31);
   if(lots <= 0.0)
     {
      WriteAck(commandId, "REJECT", "lot is outside the broker limits");
      return;
     }
   if(sl <= 0.0)
     {
      WriteAck(commandId, "REJECT", "a hard stop is required");
      return;
     }
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   if(bid <= 0.0 || ask < bid)
     {
      WriteAck(commandId, "REJECT", "no price");
      return;
     }
   bool buy = (action == "BUY");
   if(!buy && action != "SELL")
     {
      WriteAck(commandId, "REJECT", "action must be BUY or SELL");
      return;
     }
   if(buy && sl >= bid)
     {
      WriteAck(commandId, "REJECT", "buy stop must be below the bid");
      return;
     }
   if(!buy && sl <= ask)
     {
      WriteAck(commandId, "REJECT", "sell stop must be above the ask");
      return;
     }
   bool sent = SendWithFilling(buy, symbol, lots, (buy ? ask : bid), sl, tp, comment);
   if(!sent)
     {
      WriteAck(commandId, "REJECT", IntegerToString((int)g_trade.ResultRetcode()));
      return;
     }
   ulong position = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      position = ticket;
      break;
     }
   WriteAck(commandId, "OK", IntegerToString((long)position));
   Print("Agent order ", action, " ", symbol, " ", DoubleToString(lots, 4), " sl ", DoubleToString(sl, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)));
  }

//+------------------------------------------------------------------+
void ReadCommand()
  {
   if(!FileIsExist("agent_cmd.txt"))
      return;
   int handle = FileOpen("agent_cmd.txt", FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(handle == INVALID_HANDLE)
      return;
   string line = FileReadString(handle);
   FileClose(handle);
   FileDelete("agent_cmd.txt");
   if(StringLen(line) > 0)
      ExecuteCommand(line);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   WriteState();
   ReadCommand();
  }

//+------------------------------------------------------------------+
void OnTick()
  {
  }
//+------------------------------------------------------------------+
