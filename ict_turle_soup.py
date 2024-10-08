// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © fluxchart
var initRun = true
//@version=5
strategy("RB ICT Turtle Soup | Flux Charts", shorttitle = "Turtle Soup | Flux Charts", overlay = true, max_boxes_count = 500, max_labels_count = 500, max_lines_count = 500, max_bars_back = 4900 + 100)
import TradingView/Strategy/3

const bool DEBUG = false
const int maxDistanceToLastBar = 4900 // Affects Running Time
const int atrLen = 5
const bool maxTPLastHour = false


//pivotLenLiq = input.int(4, "Pivot Length", group = "General Configuration", display = display.none)
mssOffset = input.int(16, "MSS Swing Length", group = "General Configuration")
higherTimeframe = input.timeframe("60", "Higher Timeframe", group = "General Configuration")
breakoutMethod = input.string("Wick", "Breakout Method", options = ["Close", "Wick"], group = "General Configuration")
entryMethod = input.string("Classic", "Entry Method", options = ["Classic", "Adaptive"], group = "General Configuration", tooltip = "The entry method for the indicator to use. Try changing this setting if you are getting poor results.")
dbgTPSLVersion = input.string("Default", "TP / SL Layout", options = ["Default", "Alternative"], group = "General Configuration")
dbgLabelSize = DEBUG ? input.string("Small", "[DBG] Label Size", ["Normal", "Small", "Tiny"], group = "General Configuration") : "Normal"
lblSize = (dbgLabelSize == "Small" ? size.small : dbgLabelSize == "Normal" ? size.normal : size.tiny)

showHL = input.bool(false, "Show Liquidity Zones", inline = "3", group = "General Configuration")
showLiqGrabs = input.bool(true, "Liq Grabs", inline = "3", group = "General Configuration")
showTPSL = input.bool(true, "TP / SL", inline = "3", group = "General Configuration")

tpslMethod = input.string("Dynamic", "TP / SL Method", options = ["Dynamic", "Fixed"], group = "TP / SL")
riskAmount = input.string("Low", "Risk", options = ["Highest", "High", "Normal", "Low", "Lowest"], group = "TP / SL", tooltip = "The risk amount when Dynamic TP / SL method is selected.\n\nDifferent assets may have different volatility so changing this setting may result in change of performance of the indicator.")
customSLATRMult = DEBUG ? input.float(6.5, "Custom Risk Mult", group = "TP / SL") : 6.5
tpPercent = input.float(0.3, "Take Profit %", group = "TP / SL")
slPercent = input.float(0.4, "Stop Loss %", group = "TP / SL")

RR = DEBUG ? input.float(0.9, "Risk:Reward Ratio", group = "Debug") : 0.9

slATRMult = riskAmount == "Highest" ? 10 : riskAmount == "High" ? 6.5 : riskAmount == "Normal" ? 5.5 : riskAmount == "Low" ? 3.5 : riskAmount == "Lowest" ? 1.15 : customSLATRMult

backtestDisplayEnabled = input.bool(true, "Enabled", group = "Backtesting Dashboard", display = display.none)
backtestingLocation = input.string("Top Center", "Position", options = ["Top Right", "Right Center", "Top Center"], group = "Backtesting Dashboard", display = display.none)
fillBackgrounds = input.bool(true, "Fill Backgrounds", group = "Backtesting Dashboard", display = display.none)
screenerColor = input.color(#1B1F2B, 'Background', inline = "1", group = 'Backtesting Dashboard', display = display.none)

highColor = input.color(color.green, "Buy", inline = "colors", group = "Visuals")
lowColor = input.color(color.red, "Sell", inline = "colors", group = "Visuals")
textColor = input.color(color.white, "Text", inline = "colors", group = "Visuals")

buyAlertEnabled = input.bool(true, "Buy Signal", inline = "BS", group = "Alerts")
sellAlertEnabled = input.bool(true, "Sell Signal", inline = "BS", group = "Alerts")
tpAlertEnabled = input.bool(true, "Take-Profit Signal", inline = "TS", group = "Alerts")
slAlertEnabled = input.bool(true, "Stop-Loss Signal ", inline = "TS", group = "Alerts")

buyAlertTick = false
sellAlertTick = false
tpAlertTick = false
slAlertTick = false


type Sweep
    int startTime
    int endTime
    string side
    float price

type TurtleSoup
    string state
    int startTime

    int lastHour = na
    float lastHourHigh = na
    float lastHourLow = na
    Sweep brokenSweep = na
    float slTarget
    float tpTarget
    string entryType
    int entryTime
    int exitTime
    float entryPrice
    float exitPrice
    int dayEndedBeforeExit


var lineX = array.new<line>()
var boxX = array.new<box>()
var labelX = array.new<label>()

var TurtleSoup[] tsList = array.new<TurtleSoup>(0)
var TurtleSoup lastTS = na

atr = ta.atr(atrLen)

diffPercent (float val1, float val2) =>
    (math.abs(val1 - val2) / val2) * 100.0

getPosition (positionText) =>
    if positionText == "Top Right"
        position.top_right
    else if positionText == "Top Center"
        position.top_center
    else if positionText == "Right Center"
        position.middle_right
    else if positionText == "Left Center"
        position.middle_left
    else if positionText == "Bottom Center"
        position.bottom_center
    else if positionText == "Middle Center"
        position.middle_center

tfInMin = timeframe.in_seconds() / 60

//#region Liqs
if timeframe.in_seconds(higherTimeframe) <= timeframe.in_seconds()
    runtime.error("Higher timeframe must be higher than current timeframe.")
int htfMins = timeframe.in_seconds(higherTimeframe) / 60
int barLength = htfMins / tfInMin
float high12 = ta.highest(barLength)
float low12 = ta.lowest(barLength)
float highMSS = ta.highest(mssOffset)
float lowMSS = ta.lowest(mssOffset)
int lastHourTime = time[barLength]
//#endregion

//#region Turtle Soup
var highBreaks = 0
var lowBreaks = 0

if bar_index > last_bar_index - maxDistanceToLastBar
    if true
        // Find Session Start
        createNewTS = true
        if not na(lastTS)
            if na(lastTS.exitPrice)
                createNewTS := false // Don't enter if a trade is already entered
                
        if createNewTS
            newTS = TurtleSoup.new("Waiting For Liquidity Break", time)
            newTS.lastHourHigh := high12
            newTS.lastHourLow := low12
            newTS.lastHour := lastHourTime
            tsList.unshift(newTS)
            lastTS := newTS
            log.info("New Turtle Soup")

        if not na(lastTS)
            // Find Liquidity Breaks
            if lastTS.state == "Waiting For Liquidity Break"
                log.info("Wait For Liq Grab")
                if time > lastTS.startTime
                    if (breakoutMethod == "Close" ? close : low) < lastTS.lastHourLow
                        log.info("Sellside Liq Grab")
                        if entryMethod == "Classic" or highBreaks > lowBreaks
                            lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Sellside", lastTS.lastHourLow)
                            lastTS.entryType := "Long"
                        else if highBreaks <= lowBreaks
                            //lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Buyside", lastTS.lastHourHigh)
                            lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Sellside", lastTS.lastHourLow)
                            lastTS.entryType := "Short"

                        lastTS.state := "Waiting For Execution"
                    
                    else if (breakoutMethod == "Close" ? close : high) > lastTS.lastHourHigh
                        log.info("Buyside Liq Grab")
                        if entryMethod == "Classic" or highBreaks <= lowBreaks
                            lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Buyside", lastTS.lastHourHigh)
                            lastTS.entryType := "Short"
                        else if highBreaks > lowBreaks
                            //lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Sellside", lastTS.lastHourLow)
                            lastTS.brokenSweep := Sweep.new(lastTS.lastHour, time, "Buyside", lastTS.lastHourHigh)
                            lastTS.entryType := "Long"
                        lastTS.state := "Waiting For Execution"
            // Execute
            if lastTS.state == "Waiting For Execution"
                if time > lastTS.brokenSweep.endTime
                    log.info("MSS Execution")
                    if lastTS.entryType == "Short"
                        if (breakoutMethod == "Close" ? close : low) < lowMSS[1]
                            sellAlertTick := true
                            lastTS.state := "Entry Taken"
                            lastTS.entryTime := time
                            lastTS.entryPrice := (breakoutMethod == "Close" ? close : lowMSS[1])
                            if tpslMethod == "Fixed"
                                lastTS.slTarget := lastTS.entryPrice * (1 + slPercent / 100.0)
                                lastTS.tpTarget := lastTS.entryPrice * (1 - tpPercent / 100.0)
                            else
                                lastTS.slTarget := highMSS + atr * slATRMult
                                lastTS.tpTarget := lastTS.entryPrice - (math.abs(lastTS.entryPrice - lastTS.slTarget) * RR)
                    else // Long
                        if (breakoutMethod == "Close" ? close : high) > highMSS[1]
                            buyAlertTick := true
                            lastTS.state := "Entry Taken"
                            lastTS.entryTime := time
                            lastTS.entryPrice := (breakoutMethod == "Close" ? close : highMSS[1])
                            if tpslMethod == "Fixed"
                                lastTS.slTarget := lastTS.entryPrice * (1 - slPercent / 100.0)
                                lastTS.tpTarget := lastTS.entryPrice * (1 + tpPercent / 100.0)
                            else
                                lastTS.slTarget := lowMSS - atr * slATRMult
                                lastTS.tpTarget := lastTS.entryPrice + (math.abs(lastTS.entryPrice - lastTS.slTarget) * RR)
    
    // Entry Taken
    if not na(lastTS)
        if lastTS.state == "Entry Taken"
            log.info("Entry Taken")
            if tpslMethod == "Fixed"
                // Take Profit
                if lastTS.entryType == "Long" and ((high / lastTS.entryPrice) - 1) * 100 >= tpPercent
                    tpAlertTick := true
                    lastTS.exitPrice := lastTS.entryPrice * (1 + tpPercent / 100.0)
                    lastTS.exitTime := time
                    lastTS.state := "Take Profit"
                    highBreaks += 1
                if lastTS.entryType == "Short" and ((low / lastTS.entryPrice) - 1) * 100 <= -tpPercent
                    tpAlertTick := true
                    lastTS.exitPrice := lastTS.entryPrice * (1 - tpPercent / 100.0)
                    lastTS.exitTime := time
                    lastTS.state := "Take Profit"
                    lowBreaks += 1
                
                // Stop Loss
                if lastTS.entryType == "Long" and ((low / lastTS.entryPrice) - 1) * 100 <= -slPercent
                    slAlertTick := true
                    lastTS.exitPrice := lastTS.entryPrice * (1 - slPercent / 100.0)
                    lastTS.exitTime := time
                    lastTS.state := "Stop Loss"
                    highBreaks -= 1
                if lastTS.entryType == "Short" and ((high / lastTS.entryPrice) - 1) * 100 >= slPercent
                    slAlertTick := true
                    lastTS.exitPrice := lastTS.entryPrice * (1 + slPercent / 100.0)
                    lastTS.exitTime := time
                    lastTS.state := "Stop Loss"
                    lowBreaks -= 1
            else
                // Take Profit
                if lastTS.entryType == "Long" and ((maxTPLastHour and high >= lastTS.lastHourHigh) or high >= lastTS.tpTarget)
                    tpAlertTick := true
                    lastTS.exitPrice := (high >= math.max(lastTS.lastHourHigh, lastTS.tpTarget) ? math.max(lastTS.lastHourHigh, lastTS.tpTarget) : math.min(lastTS.lastHourHigh, lastTS.tpTarget))
                    lastTS.exitTime := time
                    lastTS.state := "Take Profit"
                    highBreaks += 1
                if lastTS.entryType == "Short" and ((maxTPLastHour and low <= lastTS.lastHourLow) or low <= lastTS.tpTarget)
                    tpAlertTick := true
                    lastTS.exitPrice := (low <= math.min(lastTS.lastHourLow, lastTS.tpTarget) ? math.min(lastTS.lastHourLow, lastTS.tpTarget) : math.max(lastTS.lastHourLow, lastTS.tpTarget))
                    lastTS.exitTime := time
                    lastTS.state := "Take Profit"
                    lowBreaks += 1
                
                // Stop Loss
                if lastTS.entryType == "Long" and low <= lastTS.slTarget
                    slAlertTick := true
                    lastTS.exitPrice := lastTS.slTarget
                    lastTS.exitTime := time
                    lastTS.state := "Stop Loss"
                    highBreaks -= 1
                if lastTS.entryType == "Short" and high >= lastTS.slTarget
                    slAlertTick := true
                    lastTS.exitPrice := lastTS.slTarget
                    lastTS.exitTime := time
                    lastTS.state := "Stop Loss"
                    lowBreaks -= 1
//#endregion

//#region Render Turtle Soups

renderTopSL = false
renderBottomSL = false
renderTopTP = false
renderBottomTP = false

if not na(lastTS)
    if lastTS.state == "Stop Loss" and time >= lastTS.exitTime
        if lastTS.entryType == "Long"
            renderBottomSL := true
        else
            renderTopSL := true
        lastTS.state := "Done"
    if lastTS.state == "Take Profit"
        if lastTS.entryType == "Long"
            renderTopTP := true
        else
            renderBottomTP := true
        lastTS.state := "Done"

plotshape(renderTopSL, "", shape.circle, location.abovebar, color.red, textcolor = textColor, text = "SL", size = size.tiny)
plotshape(renderBottomSL, "", shape.circle, location.belowbar, color.red, textcolor = textColor, text = "SL", size = size.tiny)
plotshape(renderTopTP, "", shape.xcross, location.abovebar, color.blue, textcolor = textColor, text = "TP", size = size.tiny)
plotshape(renderBottomTP, "", shape.xcross, location.belowbar, color.blue, textcolor = textColor, text = "TP", size = size.tiny)

//#endregion

//#region Alerts
if barstate.islastconfirmedhistory
    initRun := false

alertcondition(buyAlertTick and not initRun, "Buy Signal", "")
alertcondition(sellAlertTick and not initRun, "Sell Signal", "")
alertcondition(tpAlertTick and not initRun, "Take-Profit Signal", "")
alertcondition(slAlertTick and not initRun, "Stop-Loss Signal", "")

length = input(title="Length", defval=45)
offset = input(title="Offset", defval=0)
src = input(close, title="Source")
lsma = ta.linreg(src, length, offset)
lsma2 = ta.linreg(lsma, length, offset)
eq= lsma-lsma2
zlsma = lsma+eq

bool isZlsmaLong = close > zlsma 
bool isZlsmaShort = close < zlsma 
if initRun
    if buyAlertTick and isZlsmaLong and buyAlertEnabled
        alert("Buy Signal")
        strategy.entry("LongTrade", strategy.long, comment = "")
    if sellAlertTick and isZlsmaShort and sellAlertEnabled
        alert("Sell Signal")
        strategy.entry("ShortTrade", strategy.short, comment = "")
    if tpAlertTick and tpAlertEnabled
        alert("Take-Profit Signal")
        if (strategy.position_size > 0)
            strategy.close("LongTrade", comment = "")
        else if (strategy.position_size < 0)
            strategy.close("ShortTrade", comment = "")
    if slAlertTick and slAlertEnabled
        alert("Stop-Loss Signal")
        if (strategy.position_size > 0)
            strategy.close("LongTrade", comment = "")
        else if (strategy.position_size < 0)
            strategy.close("ShortTrade", comment = "")
    

//#endregion

if barstate.isconfirmed
    if lineX.size() > 0
        for i = 0 to lineX.size() - 1
            line.delete(lineX.get(i))

    if boxX.size() > 0
        for i = 0 to boxX.size() - 1
            box.delete(boxX.get(i))
    
    if labelX.size() > 0
        for i = 0 to labelX.size() - 1
            label.delete(labelX.get(i))

    lineX.clear()
    boxX.clear()
    labelX.clear()
    
    if tsList.size() > 0
        for i = 0 to math.min(125, tsList.size() - 1)
            curTS = tsList.get(i)

            // Target Liquidity
            if not na(curTS.brokenSweep) and showHL
                offset = atr / 3.0
                if curTS.brokenSweep.price == curTS.lastHourHigh
                    boxX.push(box.new(curTS.brokenSweep.startTime, curTS.lastHourHigh + offset, curTS.brokenSweep.endTime, curTS.lastHourHigh - offset, text = "TARGET LIQUIDITY (" + str.tostring(higherTimeframe) + ")", text_color = textColor, xloc = xloc.bar_time, border_width = 0, bgcolor = color.new(highColor, 50), text_size = size.small))
                    //lineX.push(line.new(curTS.brokenSweep.startTime, curTS.lastHourHigh, curTS.brokenSweep.endTime, curTS.lastHourHigh, xloc = xloc.bar_time, color = lowColor, style = line.style_dashed))
                else
                    boxX.push(box.new(curTS.brokenSweep.startTime, curTS.lastHourLow + offset, curTS.brokenSweep.endTime, curTS.lastHourLow - offset, text = "TARGET LIQUIDITY (" + str.tostring(higherTimeframe) + ")", text_color = textColor, xloc = xloc.bar_time, border_width = 0, bgcolor = color.new(lowColor, 50), text_size = size.small))
                    //lineX.push(line.new(curTS.brokenSweep.startTime, curTS.lastHourLow, curTS.brokenSweep.endTime, curTS.lastHourLow, xloc = xloc.bar_time, color = highColor, style = line.style_dashed))

            // Liq Grab
            if not na(curTS.brokenSweep) and showLiqGrabs
                if curTS.brokenSweep.price == curTS.lastHourHigh
                    labelX.push(label.new(curTS.brokenSweep.endTime, high, yloc = yloc.abovebar, xloc = xloc.bar_time, style = label.style_circle, size = size.tiny, color = color.new(lowColor, 50)))
                else
                    labelX.push(label.new(curTS.brokenSweep.endTime, low, yloc = yloc.belowbar, xloc = xloc.bar_time, style = label.style_circle, size = size.tiny, color = color.new(highColor, 50)))

            if not na(curTS.entryTime)
                // Entry Label
                if curTS.entryType == "Long"
                    labelX.push(label.new(curTS.entryTime, close, "Buy", xloc = xloc.bar_time, yloc = yloc.belowbar, textcolor = textColor, color = highColor, style = label.style_label_up, size = lblSize))
                else
                    labelX.push(label.new(curTS.entryTime, close, "Sell", xloc = xloc.bar_time, yloc = yloc.abovebar, textcolor = textColor, color = lowColor, style = label.style_label_down, size = lblSize))
            
            // TP / SL
            if not na(curTS.entryTime)
                if showTPSL
                    if dbgTPSLVersion == "Alternative"
                        offset = atr / 3.0
                        endTime = nz(curTS.exitTime, time("", -15))
                        boxX.push(box.new(curTS.entryTime, curTS.tpTarget + offset, endTime, curTS.tpTarget - offset, text = "TAKE PROFIT (" + str.tostring(curTS.tpTarget, format.mintick) + ")", text_color = textColor, xloc = xloc.bar_time, border_width = 0, bgcolor = color.new(highColor, 50), text_size = size.small))
                        boxX.push(box.new(curTS.entryTime, curTS.slTarget + offset, endTime, curTS.slTarget - offset, text = "STOP LOSS (" + str.tostring(curTS.slTarget, format.mintick) + ")", text_color = textColor, xloc = xloc.bar_time, border_width = 0, bgcolor = color.new(lowColor, 50) , text_size = size.small))
                    else if dbgTPSLVersion == "Default"
                        endTime = nz(curTS.exitTime, time("", -15))
                        lineX.push(line.new(curTS.entryTime, curTS.entryPrice, curTS.entryTime, curTS.tpTarget, xloc = xloc.bar_time, color = highColor, style = line.style_dashed))
                        lineX.push(line.new(curTS.entryTime, curTS.tpTarget, endTime, curTS.tpTarget, xloc = xloc.bar_time, color = highColor, style = line.style_dashed))
                        labelX.push(label.new(endTime, curTS.tpTarget, "TP", xloc = xloc.bar_time, yloc = yloc.price, textcolor = textColor, color = color.new(highColor, 50), style = label.style_label_left, size = lblSize))
                        //
                        lineX.push(line.new(curTS.entryTime, curTS.entryPrice, curTS.entryTime, curTS.slTarget, xloc = xloc.bar_time, color = lowColor, style = line.style_dashed))
                        lineX.push(line.new(curTS.entryTime, curTS.slTarget, endTime, curTS.slTarget, xloc = xloc.bar_time, color = lowColor, style = line.style_dashed))
                        labelX.push(label.new(endTime, curTS.slTarget, "SL", xloc = xloc.bar_time, yloc = yloc.price, textcolor = textColor, color = color.new(lowColor, 50), style = label.style_label_left, size = lblSize))

            if not na(curTS.dayEndedBeforeExit)
                labelX.push(label.new(curTS.dayEndedBeforeExit, close, "Exit", xloc = xloc.bar_time, yloc = yloc.belowbar, textcolor = textColor, color = color.yellow, style = label.style_circle, size = size.tiny))

//#region Backtesting Dashboard

if barstate.islast and backtestDisplayEnabled
    var table backtestDisplay = table.new(getPosition(backtestingLocation), 2, 10, bgcolor = screenerColor, frame_width = 2, frame_color = color.black, border_width = 1, border_color = color.black)
    
    float totalTSProfitPercent = 0
    int successfulTrades = 0
    int unsuccessfulTrades = 0

    if tsList.size() > 0
        for i = 0 to tsList.size() - 1
            curTS = tsList.get(i)
            if not na(curTS.entryPrice)
                isSuccess = false
                if not na(curTS.exitPrice)
                    if (curTS.entryType == "Long" and curTS.exitPrice > curTS.entryPrice) or (curTS.entryType == "Short" and curTS.exitPrice < curTS.entryPrice)
                        totalTSProfitPercent += math.abs(diffPercent(curTS.entryPrice, curTS.exitPrice))
                        isSuccess := true
                    else
                        totalTSProfitPercent -= math.abs(diffPercent(curTS.entryPrice, curTS.exitPrice))
                        isSuccess := false

                if isSuccess
                    successfulTrades += 1
                else
                    unsuccessfulTrades += 1
    
    // Header
    table.merge_cells(backtestDisplay, 0, 0, 1, 0)
    table.cell(backtestDisplay, 0, 0, "TS Backtesting", text_color = color.white, bgcolor = screenerColor)

    // Total ORBs
    table.cell(backtestDisplay, 0, 1, "Total Entries", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 1, str.tostring(successfulTrades + unsuccessfulTrades), text_color = color.white, bgcolor = screenerColor)

    // Wins
    table.cell(backtestDisplay, 0, 2, "Wins", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 2, str.tostring(successfulTrades), text_color = color.white, bgcolor = screenerColor)

    // Losses
    table.cell(backtestDisplay, 0, 3, "Losses", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 3, str.tostring(unsuccessfulTrades), text_color = color.white, bgcolor = screenerColor)

    // Winrate
    table.cell(backtestDisplay, 0, 4, "Winrate", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 4, str.tostring(100.0 * (successfulTrades / (successfulTrades + unsuccessfulTrades)), "#.##") + "%", text_color = color.white, bgcolor = screenerColor)

    // Average Profit %
    table.cell(backtestDisplay, 0, 5, "Average Profit", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 5, str.tostring(totalTSProfitPercent / (successfulTrades + unsuccessfulTrades), "#.##") + "%", text_color = color.white, bgcolor = screenerColor)

    // Total Profit %
    table.cell(backtestDisplay, 0, 6, "Total Profit", text_color = color.white, bgcolor = screenerColor)
    table.cell(backtestDisplay, 1, 6, str.tostring(totalTSProfitPercent, "#.##") + "%", text_color = color.white, bgcolor = screenerColor)

//#endregion
