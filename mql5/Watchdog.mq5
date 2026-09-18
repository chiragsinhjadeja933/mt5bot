//+------------------------------------------------------------------+
//|                                                 Watchdog.mq5     |
//|               MT5 Demo Terminal Bot — Terminal-Side Watchdog EA  |
//|                   Independent Protective Layer (Section 50)       |
//+------------------------------------------------------------------+
#property copyright "Trading Terminal Engineering"
#property link      "https://localhost:3000"
#property version   "1.00"
#property strict

// Inputs
input ulong  InpBotMagic              = 100100;     // Bot Magic Number to monitor
input int    InpHeartbeatTimeoutSec   = 30;         // Max allowed seconds without heartbeat
input bool   InpAutoCloseOnTimeout    = true;       // Close bot positions if heartbeat lost
input string InpGlobalHeartbeatVar    = "BOT_HB";   // GlobalVariable name for heartbeat
input string InpGlobalKillVar         = "BOT_KILL"; // GlobalVariable name for emergency kill

datetime g_last_warn = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   PrintFormat("[Watchdog] Initialized. Monitoring magic=%d, timeout=%ds", 
               InpBotMagic, InpHeartbeatTimeoutSec);
   EventSetTimer(1); // 1-second timer tick
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("[Watchdog] Deinitialized.");
}

//+------------------------------------------------------------------+
//| Close all open positions matching bot magic number               |
//+------------------------------------------------------------------+
void CloseBotPositions(string reason)
{
   PrintFormat("[Watchdog] EMERGENCY ACTION: Closing all positions (magic=%d) due to: %s", 
               InpBotMagic, reason);
               
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      
      if(PositionGetInteger(POSITION_MAGIC) == InpBotMagic)
      {
         MqlTradeRequest request = {};
         MqlTradeResult  result  = {};
         
         request.action   = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol   = PositionGetString(POSITION_SYMBOL);
         request.volume   = PositionGetDouble(POSITION_VOLUME);
         request.deviation= 10;
         
         ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         if(type == POSITION_TYPE_BUY)
         {
            request.type  = ORDER_TYPE_SELL;
            request.price = SymbolInfoDouble(request.symbol, SYMBOL_BID);
         }
         else
         {
            request.type  = ORDER_TYPE_BUY;
            request.price = SymbolInfoDouble(request.symbol, SYMBOL_ASK);
         }
         
         if(OrderSend(request, result))
         {
            PrintFormat("[Watchdog] Closed position #%d successfully (retcode=%d)", 
                        ticket, result.retcode);
         }
         else
         {
            PrintFormat("[Watchdog] FAILED to close position #%d (retcode=%d)", 
                        ticket, result.retcode);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Timer function (called every 1s)                                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   datetime now = TimeLocal();
   
   // 1. Check explicit kill switch flag
   if(GlobalVariableCheck(InpGlobalKillVar))
   {
      double killVal = GlobalVariableGet(InpGlobalKillVar);
      if(killVal > 0.5)
      {
         CloseBotPositions("Global KILL flag detected");
         GlobalVariableDel(InpGlobalKillVar);
         return;
      }
   }
   
   // 2. Check heartbeat timestamp
   if(GlobalVariableCheck(InpGlobalHeartbeatVar))
   {
      datetime lastHb = (datetime)GlobalVariableGet(InpGlobalHeartbeatVar);
      int elapsed = (int)(now - lastHb);
      
      if(elapsed > InpHeartbeatTimeoutSec)
      {
         if(now - g_last_warn > 5)
         {
            PrintFormat("[Watchdog] WARNING: Heartbeat missing for %d seconds (limit=%ds)", 
                        elapsed, InpHeartbeatTimeoutSec);
            g_last_warn = now;
         }
         
         if(InpAutoCloseOnTimeout)
         {
            CloseBotPositions(StringFormat("Heartbeat lost for %d seconds", elapsed));
         }
      }
   }
}
//+------------------------------------------------------------------+
