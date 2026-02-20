#!/usr/bin/env swift

import Foundation
import iTunesLibrary

struct Options {
    var showCounts = false
    var findTitle: String?
    var cloudType: Int?
    var limit = 100
}

func usage() {
    let text = """
    Usage:
      swift scripts/cloudscan.swift --counts
      swift scripts/cloudscan.swift --find-title "Vampire Pills" [--limit 20]
      swift scripts/cloudscan.swift --cloud-type 9 [--limit 200]

    Flags:
      --counts                Show aggregate counts by cloudType/locationType/cloud.
      --find-title <text>     Case-insensitive title filter.
      --cloud-type <int>      Filter by cloudType value.
      --limit <int>           Max rows for listing output (default: 100).
      --help                  Show this message.
    """
    print(text)
}

func parseArgs(_ args: [String]) -> Options? {
    var opts = Options()
    var i = 0
    while i < args.count {
        let a = args[i]
        switch a {
        case "--counts":
            opts.showCounts = true
        case "--find-title":
            i += 1
            guard i < args.count else { return nil }
            opts.findTitle = args[i]
        case "--cloud-type":
            i += 1
            guard i < args.count, let n = Int(args[i]) else { return nil }
            opts.cloudType = n
        case "--limit":
            i += 1
            guard i < args.count, let n = Int(args[i]), n > 0 else { return nil }
            opts.limit = n
        case "--help", "-h":
            usage()
            exit(0)
        default:
            return nil
        }
        i += 1
    }
    if !opts.showCounts && opts.findTitle == nil && opts.cloudType == nil {
        opts.showCounts = true
    }
    return opts
}

func intKVC(_ item: NSObject, _ key: String) -> Int? {
    return (item.value(forKey: key) as? NSNumber)?.intValue
}

func stringKVC(_ item: NSObject, _ key: String) -> String? {
    return item.value(forKey: key) as? String
}

func printCounts(items: [ITLibMediaItem]) {
    struct Bucket {
        var count = 0
    }
    var byKey: [String: Bucket] = [:]

    for item in items {
        let obj = item as NSObject
        let ct = intKVC(obj, "cloudType") ?? -1
        let lt = Int(item.locationType.rawValue)
        let cl = item.isCloud ? 1 : 0
        let key = "cloudType=\(ct)\tlocationType=\(lt)\tcloud=\(cl)"
        var b = byKey[key] ?? Bucket()
        b.count += 1
        byKey[key] = b
    }

    let rows = byKey.map { (k: $0.key, v: $0.value.count) }.sorted { a, b in
        if a.v == b.v { return a.k < b.k }
        return a.v > b.v
    }

    print("count\tcloudType\tlocationType\tcloud")
    for row in rows {
        let parts = row.k.split(separator: "\t")
        if parts.count == 3 {
            let ct = parts[0].replacingOccurrences(of: "cloudType=", with: "")
            let lt = parts[1].replacingOccurrences(of: "locationType=", with: "")
            let cl = parts[2].replacingOccurrences(of: "cloud=", with: "")
            print("\(row.v)\t\(ct)\t\(lt)\t\(cl)")
        }
    }
}

func printList(items: [ITLibMediaItem], limit: Int) {
    print("title\tartist\talbum\tcloudType\tlocationType\tcloud\tkind\tstoreItemID")
    for item in items.prefix(limit) {
        let obj = item as NSObject
        let title = item.title
        let artist = item.artist?.name ?? ""
        let album = item.album.title ?? ""
        let ct = intKVC(obj, "cloudType") ?? -1
        let lt = Int(item.locationType.rawValue)
        let cl = item.isCloud ? 1 : 0
        let kind = item.kind ?? ""
        let storeID = intKVC(obj, "storeItemID") ?? 0
        print("\(title)\t\(artist)\t\(album)\t\(ct)\t\(lt)\t\(cl)\t\(kind)\t\(storeID)")
    }
}

guard let opts = parseArgs(Array(CommandLine.arguments.dropFirst())) else {
    usage()
    exit(2)
}

do {
    let lib = try ITLibrary(apiVersion: "1.0")
    var items = lib.allMediaItems

    if let needle = opts.findTitle?.lowercased() {
        items = items.filter { $0.title.lowercased().contains(needle) }
    }

    if let ct = opts.cloudType {
        items = items.filter {
            let obj = $0 as NSObject
            return intKVC(obj, "cloudType") == ct
        }
    }

    if opts.showCounts {
        printCounts(items: items)
        exit(0)
    }

    printList(items: items, limit: opts.limit)
} catch {
    fputs("ERROR: \(error)\n", stderr)
    exit(1)
}
