import 'dart:io';
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';

class TFLiteService {
  Interpreter? _diseaseInterpreter;
  Interpreter? _healthPestInterpreter;

  static const int imageSize = 224;

  static const List<String> diseaseLabels = [
    'Bud Root Dropping',
    'Bud Rot',
    'Gray Leaf Spot',
    'Leaf Rot',
    'Stem Bleeding',
  ];

  static const List<String> healthPestLabels = [
    'CCI_Caterpillars',
    'CCI_Leaflets',
    'Healthy_Leaves',
    'WCLWD_DryingofLeaflets',
    'WCLWD_Flaccidity',
    'WCLWD_Yellowing',
  ];

  Future<void> loadModels() async {
    _diseaseInterpreter = await Interpreter.fromAsset(
      'assets/models/coconut_disease_model.tflite',
    );

    _healthPestInterpreter = await Interpreter.fromAsset(
      'assets/models/coconut_health_pest_model.tflite',
    );

    print('✅ Disease model loaded');
    print('✅ Health/Pest model loaded');

    print(
      'Disease input: '
          '${_diseaseInterpreter!.getInputTensor(0).shape}',
    );

    print(
      'Disease output: '
          '${_diseaseInterpreter!.getOutputTensor(0).shape}',
    );

    print(
      'Health/Pest input: '
          '${_healthPestInterpreter!.getInputTensor(0).shape}',
    );

    print(
      'Health/Pest output: '
          '${_healthPestInterpreter!.getOutputTensor(0).shape}',
    );
  }

  Future<Map<String, dynamic>> predictDisease(File imageFile) async {
    if (_diseaseInterpreter == null) {
      throw Exception('Disease model is not loaded');
    }

    final bytes = await imageFile.readAsBytes();

    final img.Image? originalImage = img.decodeImage(bytes);

    if (originalImage == null) {
      throw Exception('Could not decode image');
    }

    final img.Image resizedImage = img.copyResize(
      originalImage,
      width: imageSize,
      height: imageSize,
    );

    final input = List.generate(
      1,
          (_) => List.generate(
        imageSize,
            (y) => List.generate(
          imageSize,
              (x) {
            final pixel = resizedImage.getPixel(x, y);

            return [
              pixel.r.toDouble(),
              pixel.g.toDouble(),
              pixel.b.toDouble(),
            ];
          },
        ),
      ),
    );

    final output = List.generate(
      1,
          (_) => List.filled(diseaseLabels.length, 0.0),
    );

    _diseaseInterpreter!.run(input, output);

    final probabilities = List<double>.from(output[0]);

    int bestIndex = 0;

    for (int i = 1; i < probabilities.length; i++) {
      if (probabilities[i] > probabilities[bestIndex]) {
        bestIndex = i;
      }
    }

    return {
      'label': diseaseLabels[bestIndex],
      'confidence': probabilities[bestIndex],
      'index': bestIndex,
      'probabilities': probabilities,
    };
  }

  void dispose() {
    _diseaseInterpreter?.close();
    _healthPestInterpreter?.close();

    _diseaseInterpreter = null;
    _healthPestInterpreter = null;
  }
}

/* this is teh functionality this code is doing
          Photo
            ↓
          Decode image
            ↓
          Resize to 224 × 224
            ↓
          Extract RGB values
            ↓
          Create [1,224,224,3] input
            ↓
          Mendeley TFLite model
            ↓
          5 probabilities
            ↓
          Highest probability
            ↓
          Disease name + confidence

 */