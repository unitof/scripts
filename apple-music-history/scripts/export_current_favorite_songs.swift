import Foundation
import iTunesLibrary

func field(_ value: String) -> String {
    value.replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\t", with: "\\t")
        .replacingOccurrences(of: "\r", with: "\\r")
        .replacingOccurrences(of: "\n", with: "\\n")
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    let all = arguments == ["--all-playlists"]
    guard all || arguments.isEmpty || (arguments.count == 2 && arguments[0] == "--playlist") else {
        fputs("usage: export_current_favorite_songs [--playlist NAME | --all-playlists]\n", stderr)
        exit(2)
    }
    let name = arguments.last ?? "Favorite Songs"
    let library = try ITLibrary(apiVersion: "1.1")
    if all {
        let playlists: [[String: Any]] = library.allPlaylists.map { playlist in
            let items = playlist.items.map { item in
                ["persistent_id": item.persistentID.stringValue, "title": item.title,
                 "artist": item.artist?.name ?? "", "album": item.album.title ?? "",
                 "url": item.location?.absoluteString ?? ""]
            }
            return ["persistent_id": playlist.persistentID.stringValue,
                    "name": playlist.name, "parent_id": playlist.parentID?.stringValue as Any? ?? NSNull(),
                    "kind": playlist.kind.rawValue, "distinguished_kind": playlist.distinguishedKind.rawValue,
                    "visible": playlist.isVisible, "items": items]
        }
        let payload: [String: Any] = ["schema_version": 1, "complete": true, "playlists": playlists]
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        FileHandle.standardOutput.write(data)
        fputs("# exported all \(playlists.count) playlists\n", stderr)
        exit(0)
    }
    let playlists = library.allPlaylists.filter {
        name == "Favorite Songs" ? $0.distinguishedKind.rawValue == 52 : $0.name == name
    }
    guard playlists.count == 1, let playlist = playlists.first, !playlist.items.isEmpty else {
        fputs("Expected one nonempty playlist named \(name); refusing export.\n", stderr)
        exit(1)
    }
    print("persistent_id\ttitle\tartist\talbum\turl")
    fputs("# playlist=\(playlist.name) items=\(playlist.items.count) kind=\(playlist.distinguishedKind.rawValue)\n", stderr)

    for item in playlist.items {
        let id = item.persistentID.stringValue
        let title = item.title
        let artist = item.artist?.name ?? ""
        let album = item.album.title ?? ""
        let location = item.location?.absoluteString ?? ""

        print([id, title, artist, album, location].map(field).joined(separator: "\t"))
    }
} catch {
    fputs("Music library export failed: \(error)\n", stderr)
    exit(1)
}
