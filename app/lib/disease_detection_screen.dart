import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'services/tflite_service.dart';

class DiseaseDetectionScreen extends StatefulWidget {
  const DiseaseDetectionScreen({super.key});

  @override
  State<DiseaseDetectionScreen> createState() =>
      _DiseaseDetectionScreenState();
}

class _DiseaseDetectionScreenState
    extends State<DiseaseDetectionScreen> {
  final ImagePicker _picker = ImagePicker();
  final TFLiteService _tfliteService = TFLiteService();

  File? _selectedImage;

  bool _modelsReady = false;
  bool _isAnalyzing = false;

  String? _prediction;
  double? _confidence;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadModels();
  }

  Future<void> _loadModels() async {
    try {
      await _tfliteService.loadModels();

      if (!mounted) return;

      setState(() {
        _modelsReady = true;
      });
    } catch (e) {
      debugPrint('❌ Model loading failed: $e');

      if (!mounted) return;

      setState(() {
        _errorMessage = 'Could not load AI models.';
      });
    }
  }

  Future<void> _takePhoto() async {
    final XFile? image = await _picker.pickImage(
      source: ImageSource.camera,
    );

    if (image == null) return;

    if (!mounted) return;

    setState(() {
      _selectedImage = File(image.path);
      _prediction = null;
      _confidence = null;
      _errorMessage = null;
    });
  }

  Future<void> _chooseFromGallery() async {
    final XFile? image = await _picker.pickImage(
      source: ImageSource.gallery,
    );

    if (image == null) return;

    if (!mounted) return;

    setState(() {
      _selectedImage = File(image.path);
      _prediction = null;
      _confidence = null;
      _errorMessage = null;
    });
  }

  Future<void> _analyzeImage() async {
    if (_selectedImage == null) return;

    if (!_modelsReady) {
      setState(() {
        _errorMessage = 'AI model is still loading. Please wait.';
      });
      return;
    }

    setState(() {
      _isAnalyzing = true;
      _prediction = null;
      _confidence = null;
      _errorMessage = null;
    });

    try {
      final result = await _tfliteService.predictDisease(
        _selectedImage!,
      );

      if (!mounted) return;

      setState(() {
        _prediction = result['label'] as String;
        _confidence = result['confidence'] as double;
        _isAnalyzing = false;
      });
    } catch (e) {
      debugPrint('❌ Prediction failed: $e');

      if (!mounted) return;

      setState(() {
        _isAnalyzing = false;
        _errorMessage = 'Could not analyze this image.';
      });
    }
  }

  @override
  void dispose() {
    _tfliteService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F7F5),

      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(
            Icons.arrow_back_ios_new_rounded,
            color: Color(0xFF1D1D1F),
          ),
          onPressed: () {
            Navigator.pop(context);
          },
        ),
        title: const Text(
          'Disease Detection',
          style: TextStyle(
            color: Color(0xFF1D1D1F),
            fontSize: 20,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),

      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Check your coconut',
                style: TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.8,
                ),
              ),

              const SizedBox(height: 8),

              const Text(
                'Take a clear photo of the affected leaf, '
                    'bud or stem and let CocoCare analyze it.',
                style: TextStyle(
                  fontSize: 16,
                  height: 1.45,
                  color: Color(0xFF8E8E93),
                ),
              ),

              const SizedBox(height: 24),

              Expanded(
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(30),
                    border: Border.all(
                      color: const Color(0xFFE5E5E5),
                    ),
                  ),
                  child: _selectedImage == null
                      ? Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 90,
                        height: 90,
                        decoration: BoxDecoration(
                          color: const Color(0xFF34C759)
                              .withValues(alpha: 0.10),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.camera_alt_rounded,
                          size: 40,
                          color: Color(0xFF34C759),
                        ),
                      ),
                      const SizedBox(height: 22),
                      const Text(
                        'No image selected',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Use your camera or choose\n'
                            'an image from your gallery.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 14,
                          height: 1.4,
                          color: Color(0xFF8E8E93),
                        ),
                      ),
                    ],
                  )
                      : ClipRRect(
                    borderRadius: BorderRadius.circular(30),
                    child: Image.file(
                      _selectedImage!,
                      width: double.infinity,
                      height: double.infinity,
                      fit: BoxFit.cover,
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 16),

              if (_prediction != null && _confidence != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(22),
                    border: Border.all(
                      color: const Color(0xFFE5E5E5),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Detection result',
                        style: TextStyle(
                          fontSize: 14,
                          color: Color(0xFF8E8E93),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _prediction!,
                        style: const TextStyle(
                          fontSize: 21,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF1D1D1F),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Confidence: '
                            '${(_confidence! * 100).toStringAsFixed(1)}%',
                        style: const TextStyle(
                          fontSize: 14,
                          color: Color(0xFF34C759),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),

              if (_errorMessage != null) ...[
                const SizedBox(height: 10),
                Text(
                  _errorMessage!,
                  style: const TextStyle(
                    color: Colors.redAccent,
                    fontSize: 14,
                  ),
                ),
              ],

              const SizedBox(height: 16),

              if (_selectedImage != null)
                SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: ElevatedButton.icon(
                    onPressed: _isAnalyzing ? null : _analyzeImage,
                    icon: _isAnalyzing
                        ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                        : const Icon(
                      Icons.auto_awesome_rounded,
                    ),
                    label: Text(
                      _isAnalyzing
                          ? 'Analyzing...'
                          : 'Analyze image',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF34C759),
                      foregroundColor: Colors.white,
                      disabledBackgroundColor:
                      const Color(0xFF9ED8AC),
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),

              const SizedBox(height: 10),

              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _takePhoto,
                      icon: const Icon(
                        Icons.camera_alt_rounded,
                      ),
                      label: const Text('Camera'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor:
                        const Color(0xFF1D1D1F),
                        side: const BorderSide(
                          color: Color(0xFFE0E0E0),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _chooseFromGallery,
                      icon: const Icon(
                        Icons.photo_library_outlined,
                      ),
                      label: const Text('Gallery'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor:
                        const Color(0xFF1D1D1F),
                        side: const BorderSide(
                          color: Color(0xFFE0E0E0),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/* work flow that is happening with the app

  Camera / Gallery
         ↓
  Selected image
         ↓
  224 × 224 resize
         ↓
  RGB pixels
         ↓
  Mendeley TFLite model
         ↓
  5-class prediction
         ↓
  Disease name
         ↓
  Confidence %
 */