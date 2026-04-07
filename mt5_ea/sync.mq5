//+------------------------------------------------------------------+
//|                                              MT5_Influx_Sync.mq5 |
//|                                     Copyright 2026, Daniel Mtz   |
//|                                     https://www.mql5.com         |
//+------------------------------------------------------------------+
#property copyright "Daniel Mtz"
#property link      "https://danielmtzbarba.com"
#property version   "1.00"

//input string   InpServerUrl = "http://127.0.0.1:8002"; // FastAPI Server URL (Match your MT5 Options whitelist)
input string   InpServerUrl    = "http://100.124.95.126:8002"; // FastAPI Server URL (VM)
input int      InpTimeout   = 30000;                     // Timeout (ms)
input bool     InpDoHistorical = true;                  // Backfill History on Start
input int      InpVerifyHistoryDays = 7;                // Days to Verify vs Database on start (0 to disable)
// Removed manual GMT input in favor of automatic TimeGMTOffset()

// Global variables
long ExtAccountLogin = 0;
datetime last_bar_time;
bool is_initialized = false; // Flag to prevent 4014 error in OnInit
bool should_send_last_candle = false; // Flag to communicate between Tick and Timer threads

// --- Forward Declarations ---
datetime GetSyncStatus();
void BackfillHistory(datetime start_time);
void VerifyHistory(int days);
void SendLastClosedCandle();
void CheckForRepairTask(); 
void VerifyHistoryRange(datetime start, datetime end); // NEW: Selective repair helper
bool PostCandlesJSON(string payload_json, string endpoint="/upload_candles", bool print_res=true);
long GetBrokerToUTCOffset(); // Returns offset in seconds

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print("Sync: Initializing...");
   
   // Get current account login for multi-tenant identification
   ExtAccountLogin = AccountInfoInteger(ACCOUNT_LOGIN);
   PrintFormat("Sync: Authenticated with Account ID %I64d", ExtAccountLogin);
   
   // Enable WebRequest permission in MT5 Options menu (Ctrl+O -> Expert Advisors -> Allow WebRequest)
   if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) 
   {
       Print("WARNING: Please ensure 'Allow WebRequest' is enabled in MT5 Tools -> Options.");
   }

   last_bar_time = iTime(Symbol(), PERIOD_M1, 0);

   // Initialize a 1-second timer for networking to avoid 4014 error
   EventSetTimer(1);

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(reason == REASON_REMOVE || reason == REASON_CHARTCLOSE)
     {
      GlobalVariableDel("Sync: " + Symbol());
     }
     
   EventKillTimer();
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Only trigger heavily on a new M1 bar.
   datetime current_time = iTime(Symbol(), PERIOD_M1, 0);
   if(current_time != last_bar_time)
     {
      // A new bar opened. Signal the timer thread to send the closed candle.
      should_send_last_candle = true;
      last_bar_time = current_time;
     }
  }

void OnTimer()
  {
   // 1. Handle Initialization and Backfill (Once)
   if(!is_initialized)
     {
      if(InpDoHistorical)
        {
         datetime last_db_time = GetSyncStatus();
         if(last_db_time > 0)
           {
            Print("Sync: DB found records until UTC ", TimeToString(last_db_time));
            BackfillHistory(last_db_time);
           }
         else
           {
            Print("Sync: DB appears empty. Uploading last week of history...");
            BackfillHistory(TimeCurrent() - (10000 * 60)); 
           }
        }
      
      if(InpVerifyHistoryDays > 0)
        {
         // Always perform a DEEP verification of ground-truth on startup
         Print("Sync: DB Verification...");
         VerifyHistory(InpVerifyHistoryDays);
        }
        
      is_initialized = true;
     }

   // 2. Handle Real-Time Candle Transmission (Every bar close)
   if(should_send_last_candle)
     {
      SendLastClosedCandle();
      should_send_last_candle = false;
     }
     
   // 3. Handle On-Demand Repair Requests
   CheckForRepairTask();
  }

//+------------------------------------------------------------------+
//| WebRequest Helpers                                               |
//+------------------------------------------------------------------+
// GET /sync_status
datetime GetSyncStatus()
  {
   char result[];
   string result_headers;
   string headers = ""; 
   string symbol_clean = Symbol();
   StringTrimRight(symbol_clean);
   StringToUpper(symbol_clean);
   
   string url = InpServerUrl + "/sync_status?symbol=" + symbol_clean + "&mt5_login=" + IntegerToString(ExtAccountLogin);
   Print("Sync: Polling ", url);
   
   char empty_data[];
   ResetLastError();
   int res = WebRequest("GET", url, headers, InpTimeout, empty_data, result, result_headers);
   
   if(res == 200)
     {
      string json = CharArrayToString(result);
      
      int t_index = StringFind(json, "\"last_timestamp\":\"");
      if(t_index != -1)
        {
         t_index += 18; 
         string iso_time = StringSubstr(json, t_index, 19);
         
         if(StringLen(iso_time) >= 19)
           {
            StringReplace(iso_time, "-", ".");
            StringReplace(iso_time, "T", " ");
            return StringToTime(iso_time);
           }
        }
      return 0; 
     }
   else 
     {
      Print("Sync: GET failure. res=", res, " err=", GetLastError());
      return 0;
     }
  }

// POST payload helper
// POST payload helper
bool PostCandlesJSON(string payload_json, string endpoint="/upload_candles", bool print_res=true)
  {
   char post[];
   char result[];
   
   // FIX 1: Re-add Connection: close to prevent socket caching errors
   string result_headers, headers = "Content-Type: application/json\r\nConnection: close"; 
   
   // FIX 2: Changed start_pos from 1 to 0 so the opening '{' is not truncated
   StringToCharArray(payload_json, post, 0, WHOLE_ARRAY, CP_UTF8);
   int post_size = ArraySize(post);
   if(post_size > 0 && post[post_size - 1] == 0) ArrayResize(post, post_size - 1);
   
   string url = InpServerUrl + endpoint + "?mt5_login=" + IntegerToString(ExtAccountLogin);
   int max_retries = 3;
   int retry_delay_ms = 500;

   for(int i = 0; i < max_retries; i++)
     {
      ResetLastError();
      int res = WebRequest("POST", url, headers, InpTimeout, post, result, result_headers);
      
      if(res >= 200 && res < 300) 
        {
         if(print_res) Print("Sync: [SUCCESS] to ", endpoint);
         return true;
        }
      
      if(i < max_retries - 1)
        {
      //   PrintFormat("Sync: POST Fail (res=%d, err=%d). Retrying in %dms... (%d/%d)", 
     //                res, GetLastError(), retry_delay_ms, i+1, max_retries);
         Sleep(retry_delay_ms);
         retry_delay_ms *= 2; 
        }
      else
        {
         string body = (ArraySize(result) > 0) ? StringSubstr(CharArrayToString(result), 0, 256) : "EMPTY BODY";
         PrintFormat("Sync: [CRITICAL] WebRequest Failed. res=%d, err=%d", res, GetLastError());
        }
     }
     
   return false;
  }
  
// Helper to calculate seconds between Broker Time and UTC (GMT)
long GetBrokerToUTCOffset() 
  {
   // Dynamically calculate the offset between Broker time and UTC
   return (long)(TimeTradeServer() - TimeGMT());
  }

void BackfillHistory(datetime start_time_utc)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, false); 
   
   datetime start_time_broker = start_time_utc + (datetime)GetBrokerToUTCOffset();
   int copied = CopyRates(Symbol(), PERIOD_M1, start_time_broker, TimeCurrent(), rates);
   
   if(copied > 0)
     {
      Print("Backfilling ", copied, " historical bars...");
      
      int chunk_size = 1000;
      for(int i = 0; i < copied; i += chunk_size)
        {
         int end_idx = (int)MathMin(i + chunk_size, copied);
         
         // FIX: Use native escaped double quotes 
         string payload = StringFormat(
             "{\"symbol\":\"%s\",\"timeframe\":\"M1\",\"gmt_offset\":%d,\"candles\":[",
             Symbol(), GetBrokerToUTCOffset()
         );
         
         for(int j = i; j < end_idx; j++)
           {
            // Send RAW broker time and the offset - Server will handle UTC conversion
            string ts = TimeToString(rates[j].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
            
            StringReplace(ts, ".", "-");
            StringReplace(ts, " ", "T");
            
            // FIX: Using escaped quotes for robust JSON
            string bar_json = StringFormat(
               "{\"timestamp\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
               ts, rates[j].open, rates[j].high, rates[j].low, rates[j].close, rates[j].tick_volume
            );
            
            payload += bar_json;
              
            if(j < end_idx - 1) payload += ",";
           }
         payload += "]}";
         
         bool ok = PostCandlesJSON(payload, "/upload_candles", false);
         if(!ok) break; 
         Sleep(100);
        }
      Print("Backfill complete.");
     }
  }

void VerifyHistory(int days)
  {
   Print("Sync: Constructing ", days, " days payload for database verification...");
   datetime start_time_broker = TimeCurrent() - (days * 24 * 60 * 60);
   
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(Symbol(), PERIOD_M1, start_time_broker, TimeCurrent(), rates);
   
   if(copied > 0)
     {
      int chunk_size = 1000;
      for(int i = 0; i < copied; i += chunk_size)
        {
         int end_idx = (int)MathMin(i + chunk_size, copied);
         string payload = StringFormat(
            "{\"symbol\":\"%s\",\"timeframe\":\"M1\",\"gmt_offset\":%d,\"candles\":[",
            Symbol(), GetBrokerToUTCOffset()
         );
         
         for(int j = i; j < end_idx; j++)
           {
            string ts = TimeToString(rates[j].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
            StringReplace(ts, ".", "-");
            StringReplace(ts, " ", "T");
            
            string bar_json = StringFormat(
               "{\"timestamp\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
               ts, rates[j].open, rates[j].high, rates[j].low, rates[j].close, rates[j].tick_volume
            );
            payload += bar_json;
              
            if(j < end_idx - 1) payload += ",";
           }
         payload += "]}";
         
         bool ok = PostCandlesJSON(payload, "/verify_history", false);
         if(!ok) break; 
         // Allow the terminal networking thread to breathe
         Sleep(100);
        }
      Print("Sync: Verification and Repair complete for ", copied, " bars.");
     }
  }
void SendLastClosedCandle()
  {
   MqlRates rates[];
   int copied = CopyRates(Symbol(), PERIOD_M1, 1, 1, rates);
    if(copied == 1)
      {
       // Correct the bar time to UTC before uploading
       string ts = TimeToString(rates[0].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
       
       StringReplace(ts, ".", "-");
       StringReplace(ts, " ", "T");
       // Removed ts += "Z" to send as naive
      
      string payload = StringFormat(
         "{\"symbol\":\"%s\",\"timeframe\":\"M1\",\"gmt_offset\":%d,\"candles\":[",
         Symbol(), GetBrokerToUTCOffset()
      );
      
      string bar_json = StringFormat(
         "{\"timestamp\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
         ts, rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].tick_volume
      );
      
      payload += bar_json;
      payload += "]}";
      
      PostCandlesJSON(payload);
     }
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Poll server for repair requests (Selective Gaps)                 |
//+------------------------------------------------------------------+
void CheckForRepairTask()
{
   static datetime last_check = 0;
   if(TimeCurrent() - last_check < 300) return;
   last_check = TimeCurrent();
   
   char result[];
   string result_headers, headers = ""; 
   string url = InpServerUrl + "/check_repair?symbol=" + Symbol() + "&mt5_login=" + IntegerToString(ExtAccountLogin);
   
   char empty_data[];
   int res = WebRequest("GET", url, headers, 5000, empty_data, result, result_headers);
   
   if(res == 200)
     {
      string response = CharArrayToString(result);
      if(StringFind(response, "\"repair\":true") != -1)
        {
         Print("Sync: Server requested repair...");
         
         // Basic "Pseudo-JSON" parsing for gaps: [{"start":"ISO", "end":"ISO"}, ...]
         // We loop through the response string to find all "start" and "end" keys
         int pos = 0;
         while((pos = StringFind(response, "\"start\":\"", pos)) != -1)
           {
            pos += 9;
            string start_iso = StringSubstr(response, pos, 19);
            int end_pos = StringFind(response, "\"end\":\"", pos);
            if(end_pos == -1) break;
            end_pos += 7;
            string end_iso = StringSubstr(response, end_pos, 19);
            
            // Convert ISO back to datetime (Naive Broker Time)
            StringReplace(start_iso, "-", ".");
            StringReplace(start_iso, "T", " ");
            StringReplace(end_iso, "-", ".");
            StringReplace(end_iso, "T", " ");
            
            datetime dt_start_utc = StringToTime(start_iso);
            datetime dt_end_utc = StringToTime(end_iso);
            
            // CONVERT: Server Time (UTC) -> Broker Time (Local)
            // CopyRates expects the datetime parameters to match the Terminal's time
            datetime dt_start_broker = dt_start_utc + (datetime)GetBrokerToUTCOffset();
            datetime dt_end_broker = dt_end_utc + (datetime)GetBrokerToUTCOffset();
            
            if(dt_start_utc > 0 && dt_end_utc > 0)
              {
               Print("Repairing UTC gap: ", start_iso, " (Broker: ", TimeToString(dt_start_broker), ")");
               VerifyHistoryRange(dt_start_broker, dt_end_broker);
              }
            pos = end_pos;
           }
        }
     }
}

//+------------------------------------------------------------------+
//| Fetch and upload a specific range from MT5                       |
//+------------------------------------------------------------------+
void VerifyHistoryRange(datetime start_broker, datetime end_broker)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   
   // End is exclusive in CopyRates if using (start, end) overload? 
   // We use (start, count) or (start, time)
   int copied = CopyRates(Symbol(), PERIOD_M1, start_broker, end_broker + 60, rates);
   
   if(copied <= 0)
     {
      PrintFormat("Sync: Gap range [%s to %s] NOT FOUND in MT5 history.", 
                  TimeToString(start_broker), TimeToString(end_broker));
      return;
     }
     
   if(copied > 0)
     {
      string payload = StringFormat(
         "{\"symbol\":\"%s\",\"timeframe\":\"M1\",\"gmt_offset\":%d,\"candles\":[",
         Symbol(), GetBrokerToUTCOffset()
      );
      
      for(int i = 0; i < copied; i++)
        {
         string ts = TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
         StringReplace(ts, ".", "-");
         StringReplace(ts, " ", "T");
         
         string bar_json = StringFormat(
            "{\"timestamp\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
            ts, rates[i].open, rates[i].high, rates[i].low, rates[i].close, rates[i].tick_volume
         );
         payload += bar_json;
         if(i < copied - 1) payload += ",";
        }
      payload += "]}";
      PostCandlesJSON(payload, "/verify_history", false);
     }
}
