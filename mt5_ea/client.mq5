//+------------------------------------------------------------------+
//|                                           MT5_FastAPI_Client.mq5 |
//|                                     Copyright 2026, Daniel Mtz   |
//|                                     https://danielmtzbarba.com   |
//+------------------------------------------------------------------+
#property copyright "Daniel Mtz"
#property link      "https://danielmtzbarba.com"
#property version   "1.00"

#include <Trade\Trade.mqh>

//input string   InpServerUrl    = "http://127.0.0.1:8002"; // FastAPI Server URL
input string   InpServerUrl    = "http://100.124.95.126:8002"; // FastAPI Server URL (VM)
input int      InpTimeout      = 5000;                    // Timeout (ms)
input int      InpPollInterval = 5;                       // Polling Interval (Seconds)
long           ExtAccountLogin = 0;                       // Current MT5 ID

// Global Trade object
CTrade trade;

// --- Forward Declarations ---
void PollForCommands();
void SendOpenPositions();
void NotifyServerPositionOpened(long ticket, string sym, long type, double vol, double price);
void NotifyServerPositionClosed(long ticket, double profit);
bool PostJSON(string payload_json, string endpoint="/report", bool print_res=true);
string ExtractJSONString(string json, string key);
double ExtractJSONNumber(string json, string key);

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print("Client: Initializing Execution Engine...");
   
   // Store current login for backend authorization
   ExtAccountLogin = AccountInfoInteger(ACCOUNT_LOGIN);
   PrintFormat("Client: Multi-Tenant Mode Active (MT5 ID: %I64d)", ExtAccountLogin);
   
   if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) 
     {
      Print("WARNING: Please ensure 'Allow WebRequest' is enabled in MT5 Tools -> Options.");
     }

   EventSetTimer(InpPollInterval);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   Print("Client: Shutting down.");
  }

//+------------------------------------------------------------------+
//| Expert timer function (Polling Loop)                             |
//+------------------------------------------------------------------+
void OnTimer()
  {
   PollForCommands();
  }

//+------------------------------------------------------------------+
//| Trade Transaction Event (Fires instantly on trade open & close)  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
     {
      if(HistoryDealSelect(trans.deal))
        {
         long dealEntry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
         
         if(dealEntry == DEAL_ENTRY_OUT)
           {
            long ticket = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
            double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
            
            PrintFormat("Client: Position %I64d closed. Notifying server.", ticket);
            NotifyServerPositionClosed(ticket, profit);
           }
         else if(dealEntry == DEAL_ENTRY_IN)
           {
            long ticket = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
            string sym = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
            long type = HistoryDealGetInteger(trans.deal, DEAL_TYPE); // 0 = Buy, 1 = Sell
            double vol = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
            double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
            
            PrintFormat("Client: Position %I64d opened. Notifying server.", ticket);
            NotifyServerPositionOpened(ticket, sym, type, vol, price);
           }
        }
     }
  }
  
//+------------------------------------------------------------------+
//| Polling & Execution Logic                                        |
//+------------------------------------------------------------------+
void PollForCommands()
  {
   char result[];
   string result_headers;
   string headers = "";
   string url = InpServerUrl + "/poll?mt5_login=" + IntegerToString(ExtAccountLogin) + "&buster=" + IntegerToString(GetTickCount64());
   char empty_data[];
   
   ResetLastError();
   int res = WebRequest("GET", url, headers, 1000, empty_data, result, result_headers);
   
   if(res == 200)
     {
      string raw_json = CharArrayToString(result);
      
      // NEUTRALIZE WHITESPACE
      string json = raw_json;
      StringReplace(json, " ", ""); 
      
      if(StringFind(json, "\"action\":\"NONE\"") != -1) return;
      
      Print("=========================================");
      Print("DEBUG [Poll]: Server replied with 200 OK");
      Print("DEBUG [Raw JSON]: ", raw_json);
      Print("DEBUG [Clean JSON]: ", json);
      
      // Check for REPORT command
      if(StringFind(json, "\"action\":\"REPORT\"") != -1)
        {
         Print("DEBUG [Action]: Executing REPORT routine.");
         SendOpenPositions();
         return;
        }
        
      // Check for CLOSE command
      if(StringFind(json, "\"action\":\"CLOSE\"") != -1)
        {
         long ticket = (long)ExtractJSONNumber(json, "ticket"); 
         Print("DEBUG [Action]: CLOSE command triggered. Parsed Ticket: ", ticket);
         
         if(ticket > 0) 
           {
            trade.PositionClose(ticket);
            Print("DEBUG [Execution]: Sent Close request for ticket.");
           }
         else 
           {
            Print("DEBUG [ERROR]: Ticket number parsed as 0. Cannot close.");
           }
         return;
        }
        
      // Check for explicit BUY command
      if(StringFind(json, "\"action\":\"BUY\"") != -1)
        {
         Print("DEBUG [Action]: BUY command triggered.");
         
         string sym = ExtractJSONString(json, "symbol");
         double vol = ExtractJSONNumber(json, "volume");
         
         PrintFormat("DEBUG [Parsed Variables]: Symbol='%s', Volume=%.2f", sym, vol);
         
         if(sym == "" || vol <= 0)
           {
            Print("DEBUG [ERROR]: Invalid symbol or volume. Aborting execution.");
            return;
           }
         
         double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
         Print("DEBUG [Execution]: Sending BUY command to broker...");
         trade.Buy(vol, sym, ask, 0, 0, "API Buy");
         return;
        }

      // Check for explicit SELL command
      if(StringFind(json, "\"action\":\"SELL\"") != -1)
        {
         Print("DEBUG [Action]: SELL command triggered.");
         
         string sym = ExtractJSONString(json, "symbol");
         double vol = ExtractJSONNumber(json, "volume");
         
         PrintFormat("DEBUG [Parsed Variables]: Symbol='%s', Volume=%.2f", sym, vol);
         
         if(sym == "" || vol <= 0)
           {
            Print("DEBUG [ERROR]: Invalid symbol or volume. Aborting execution.");
            return;
           }
         
         double bid = SymbolInfoDouble(sym, SYMBOL_BID);
         Print("DEBUG [Execution]: Sending SELL command to broker...");
         trade.Sell(vol, sym, bid, 0, 0, "API Sell");
         return;
        }
        
      Print("DEBUG [WARNING]: Valid JSON received, but no recognizable action matched.");
     }
   else 
     {
      if(res != 4060 && res != 5203 && res != 1003) 
        {
         PrintFormat("DEBUG [HTTP Error]: res=%d, err=%d, headers: %s", res, GetLastError(), result_headers);
        }
     }
  }

//+------------------------------------------------------------------+
//| Reporting Logic                                                  |
//+------------------------------------------------------------------+
void SendOpenPositions()
  {
   string payload = "{\"positions\":[";
   int total = PositionsTotal();
   
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
        {
         string sym = PositionGetString(POSITION_SYMBOL);
         long type = PositionGetInteger(POSITION_TYPE);
         double vol = PositionGetDouble(POSITION_VOLUME);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double profit = PositionGetDouble(POSITION_PROFIT);
         
         string pos_json = StringFormat(
            "{\"ticket\":%I64d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price_open\":%.5f,\"profit\":%.2f}",
            ticket, sym, type, vol, open_price, profit
         );
         
         payload += pos_json;
         if(i < total - 1) payload += ",";
        }
     }
   payload += "]}";
   
   PostJSON(payload, "/report", true);
  }
  
void NotifyServerPositionClosed(long ticket, double profit)
  {
   string payload = StringFormat("{'ticket':%I64d,'action':'CLOSED','profit':%.2f}", ticket, profit);
   StringReplace(payload, "'", CharToString(34));
   PostJSON(payload, "/position_closed", true);
  }

void NotifyServerPositionOpened(long ticket, string sym, long type, double vol, double price)
  {
   string payload = StringFormat(
      "{'ticket':%I64d,'action':'OPENED','symbol':'%s','type':%d,'volume':%.2f,'price':%.5f}",
      ticket, sym, (int)type, vol, price
   );
   StringReplace(payload, "'", CharToString(34));
   PostJSON(payload, "/position_opened", true);
  }
  
//+------------------------------------------------------------------+
//| WebRequest POST Helper                                           |
//+------------------------------------------------------------------+
bool PostJSON(string payload_json, string endpoint="/report", bool print_res=true)
  {
   char post[];
   char result[];
   
   string result_headers, headers = "Content-Type: application/json\r\nConnection: close"; 
   
   StringToCharArray(payload_json, post, 0, WHOLE_ARRAY, CP_UTF8);
   int post_size = ArraySize(post);
   if(post_size > 0 && post[post_size - 1] == 0) ArrayResize(post, post_size - 1);
   
   string url = InpServerUrl + endpoint + "?mt5_login=" + IntegerToString(ExtAccountLogin);
   
   ResetLastError();
   int res = WebRequest("POST", url, headers, InpTimeout, post, result, result_headers);
   
   if(res >= 200 && res < 300) 
     {
      if(print_res) Print("Client: [SUCCESS] Posted to ", endpoint);
      return true;
     }
   else
     {
      PrintFormat("Client: [CRITICAL] WebRequest Failed. res=%d, err=%d", res, GetLastError());
      return false;
     }
  }

//+------------------------------------------------------------------+
//| Lightweight JSON Parsers                                         |
//+------------------------------------------------------------------+
string ExtractJSONString(string json, string key)
  {
   int pos = StringFind(json, "\"" + key + "\":\"");
   if(pos == -1) return "";
   pos += StringLen(key) + 4; 
   int end = StringFind(json, "\"", pos);
   return StringSubstr(json, pos, end - pos);
  }

double ExtractJSONNumber(string json, string key)
  {
   int pos = StringFind(json, "\"" + key + "\":");
   if(pos == -1) return 0;
   pos += StringLen(key) + 3;
   
   int end1 = StringFind(json, ",", pos);
   int end2 = StringFind(json, "}", pos);
   int end = (end1 != -1 && end1 < end2) ? end1 : end2;
   if(end == -1) end = end2;
   
   return StringToDouble(StringSubstr(json, pos, end - pos));
  }
//+------------------------------------------------------------------+