import Foundation
import iTunesLibrary

func field(_ value: String) -> String {
    value.replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\t", with: "\\t")
        .replacingOccurrences(of: "\r", with: "\\r")
        .replacingOccurrences(of: "\n", with: "\\n")
}

do {
    let library = try ITLibrary(apiVersion: "1.1")
    let playlists = library.allPlaylists.filter { $0.distinguishedKind.rawValue == 52 }
    guard playlists.count == 1, let playlist = playlists.first, !playlist.items.isEmpty else {
        fputs("Expected one nonempty built-in Favorite Songs playlist; refusing export.\n", stderr)
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
