// Keeps only the rules WebKit accepts. One bad rule makes a whole content rule
// list fail to compile in the app, so each candidate is compiled on its own.
// Usage: swift rulecheck.swift <candidates.json> <checked.json>
import WebKit

let args = CommandLine.arguments
let input = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[1]))) as! [String: Any]
let store = WKContentRuleListStore(url: URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("rulecheck"))!

func rule(block f: String) -> [String: Any] { ["trigger": ["url-filter": f], "action": ["type": "block"]] }
func rule(hide s: String) -> [String: Any] {
    ["trigger": ["url-filter": ".*", "if-domain": ["*youtube.com"]], "action": ["type": "css-display-none", "selector": s]]
}

var pending: [(kind: String, value: String)] =
    (input["block"] as? [String] ?? []).map { ("block", $0) } + (input["hide"] as? [String] ?? []).map { ("hide", $0) }
var kept: [String: [String]] = ["block": [], "hide": []]
var index = 0

func next() {
    guard index < pending.count else {
        var out = input
        out["block"] = kept["block"]; out["hide"] = kept["hide"]
        try! JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted]).write(to: URL(fileURLWithPath: args[2]))
        print("kept \(kept["block"]!.count) block, \(kept["hide"]!.count) hide of \(pending.count) candidates")
        exit(0)
    }
    let item = pending[index]; index += 1
    let r = item.kind == "block" ? rule(block: item.value) : rule(hide: item.value)
    let json = String(data: try! JSONSerialization.data(withJSONObject: [r]), encoding: .utf8)!
    store.compileContentRuleList(forIdentifier: "c\(index)", encodedContentRuleList: json) { list, _ in
        if list != nil { kept[item.kind]!.append(item.value) } else { print("dropped \(item.kind): \(item.value)") }
        next()
    }
}
next()
RunLoop.main.run(until: Date().addingTimeInterval(600))
exit(1)
