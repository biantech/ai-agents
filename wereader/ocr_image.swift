import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("Usage: ocr_image <image-path>\n".utf8))
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard let image = NSImage(contentsOf: imageURL),
      let imageData = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: imageData),
      let cgImage = bitmap.cgImage else {
    FileHandle.standardError.write(Data("Could not load image\n".utf8))
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US", "zh-Hans"]
request.usesLanguageCorrection = true

do {
    try VNImageRequestHandler(cgImage: cgImage).perform([request])
    let observations = request.results ?? []
    let lines = observations.compactMap { $0.topCandidates(1).first?.string }
    FileHandle.standardOutput.write(Data((lines.joined(separator: "\n") + "\n").utf8))
} catch {
    FileHandle.standardError.write(Data("OCR failed: \(error)\n".utf8))
    exit(1)
}
