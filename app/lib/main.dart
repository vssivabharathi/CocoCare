import 'dart:ui';
import 'package:flutter/material.dart';
import 'disease_detection_screen.dart';

void main() {
  runApp(const CocoCareApp());
}

class CocoCareApp extends StatelessWidget {
  const CocoCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'CocoCare',
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF6F7F5),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF34C759),
          brightness: Brightness.light,
        ),
        fontFamily: 'SF Pro Display',
      ),
      home: const HomeScreen(),
    );
  }
}

// ============================================================
// HOME SCREEN
// ============================================================

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F7F5),

      body: SafeArea(
        child: IndexedStack(
          index: selectedIndex,
          children: const [
            HomeContent(),
            PlaceholderScreen(
              title: 'Farm',
              icon: Icons.eco_rounded,
            ),
            PlaceholderScreen(
              title: 'Marketplace',
              icon: Icons.storefront_rounded,
            ),
            PlaceholderScreen(
              title: 'Profile',
              icon: Icons.person_outline_rounded,
            ),
          ],
        ),
      ),

      // --------------------------------------------------------
      // Bottom Navigation
      // --------------------------------------------------------

      bottomNavigationBar: Padding(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(28),
          child: BackdropFilter(
            filter: ImageFilter.blur(
              sigmaX: 20,
              sigmaY: 20,
            ),
            child: Container(
              height: 72,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.82),
                borderRadius: BorderRadius.circular(28),
                border: Border.all(
                  color: Colors.white,
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 25,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _NavItem(
                    icon: Icons.home_rounded,
                    label: 'Home',
                    selected: selectedIndex == 0,
                    onTap: () {
                      setState(() {
                        selectedIndex = 0;
                      });
                    },
                  ),

                  _NavItem(
                    icon: Icons.eco_rounded,
                    label: 'Farm',
                    selected: selectedIndex == 1,
                    onTap: () {
                      setState(() {
                        selectedIndex = 1;
                      });
                    },
                  ),

                  _NavItem(
                    icon: Icons.storefront_rounded,
                    label: 'Market',
                    selected: selectedIndex == 2,
                    onTap: () {
                      setState(() {
                        selectedIndex = 2;
                      });
                    },
                  ),

                  _NavItem(
                    icon: Icons.person_outline_rounded,
                    label: 'Profile',
                    selected: selectedIndex == 3,
                    onTap: () {
                      setState(() {
                        selectedIndex = 3;
                      });
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ============================================================
// HOME CONTENT
// ============================================================

class HomeContent extends StatelessWidget {
  const HomeContent({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(24, 22, 24, 30),

      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          // ----------------------------------------------------
          // Header
          // ----------------------------------------------------

          Row(
            children: [

              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [

                    Text(
                      'Good morning',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF8E8E93),
                      ),
                    ),

                    SizedBox(height: 4),

                    Text(
                      'CocoCare',
                      style: TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -1.3,
                        color: Color(0xFF1D1D1F),
                      ),
                    ),
                  ],
                ),
              ),

              // Notification
              _CircleButton(
                icon: Icons.notifications_none_rounded,
                onTap: () {},
              ),
            ],
          ),

          const SizedBox(height: 32),

          // ----------------------------------------------------
          // Main AI Detection Card
          // ----------------------------------------------------

          _DetectionCard(
            onTap: () {
              // Disease detection screen will be connected here.
            },
          ),

          const SizedBox(height: 28),

          // ----------------------------------------------------
          // Section title
          // ----------------------------------------------------

          const Text(
            'Your farm',
            style: TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5,
              color: Color(0xFF1D1D1F),
            ),
          ),

          const SizedBox(height: 14),

          // ----------------------------------------------------
          // Farm Statistics
          // ----------------------------------------------------

          Row(
            children: [

              Expanded(
                child: _StatCard(
                  icon: Icons.eco_outlined,
                  value: '24',
                  label: 'Trees',
                ),
              ),

              const SizedBox(width: 12),

              Expanded(
                child: _StatCard(
                  icon: Icons.water_drop_outlined,
                  value: 'Good',
                  label: 'Crop health',
                ),
              ),
            ],
          ),

          const SizedBox(height: 28),

          // ----------------------------------------------------
          // Quick Actions
          // ----------------------------------------------------

          const Text(
            'Quick actions',
            style: TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5,
              color: Color(0xFF1D1D1F),
            ),
          ),

          const SizedBox(height: 14),

          Row(
            children: [

              Expanded(
                child: _QuickAction(
                  icon: Icons.smart_toy_outlined,
                  title: 'AI Assistant',
                  onTap: () {},
                ),
              ),

              const SizedBox(width: 12),

              Expanded(
                child: _QuickAction(
                  icon: Icons.account_balance_wallet_outlined,
                  title: 'Expenses',
                  onTap: () {},
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          Row(
            children: [

              Expanded(
                child: _QuickAction(
                  icon: Icons.work_outline_rounded,
                  title: 'Find workers',
                  onTap: () {},
                ),
              ),

              const SizedBox(width: 12),

              Expanded(
                child: _QuickAction(
                  icon: Icons.show_chart_rounded,
                  title: 'Market price',
                  onTap: () {},
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ============================================================
// DISEASE DETECTION CARD
// ============================================================

class _DetectionCard extends StatelessWidget {
  final VoidCallback onTap;

  const _DetectionCard({
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => const DiseaseDetectionScreen(),
          ),
        );
      },

      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),

        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(30),

          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF34C759),
              Color(0xFF20A84A),
            ],
          ),

          boxShadow: [
            BoxShadow(
              color: const Color(0xFF34C759).withOpacity(0.20),
              blurRadius: 30,
              offset: const Offset(0, 15),
            ),
          ],
        ),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [

                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.local_florist_rounded,
                    color: Colors.white,
                    size: 25,
                  ),
                ),

                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.16),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'AI',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 28),

            const Text(
              'Check your coconut',
              style: TextStyle(
                color: Colors.white,
                fontSize: 27,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.8,
              ),
            ),

            const SizedBox(height: 7),

            Text(
              'Take a photo and let AI identify\ndiseases and pest conditions.',
              style: TextStyle(
                color: Colors.white.withOpacity(0.88),
                fontSize: 15,
                height: 1.45,
                fontWeight: FontWeight.w500,
              ),
            ),

            const SizedBox(height: 22),

            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 18,
                vertical: 12,
              ),

              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
              ),

              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [

                  Icon(
                    Icons.camera_alt_rounded,
                    color: Color(0xFF1D1D1F),
                    size: 19,
                  ),

                  SizedBox(width: 8),

                  Text(
                    'Scan now',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF1D1D1F),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// STAT CARD
// ============================================================

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;

  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),

      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),

        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.035),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),

      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          Icon(
            icon,
            color: const Color(0xFF34C759),
            size: 25,
          ),

          const SizedBox(height: 16),

          Text(
            value,
            style: const TextStyle(
              fontSize: 23,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5,
            ),
          ),

          const SizedBox(height: 2),

          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF8E8E93),
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
// QUICK ACTION
// ============================================================

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.title,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),

      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),

        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 17,
          ),

          child: Row(
            children: [

              Icon(
                icon,
                color: const Color(0xFF34C759),
                size: 23,
              ),

              const SizedBox(width: 11),

              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1D1D1F),
                  ),
                ),
              ),

              const Icon(
                Icons.chevron_right_rounded,
                size: 20,
                color: Color(0xFFC7C7CC),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================
// CIRCLE BUTTON
// ============================================================

class _CircleButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _CircleButton({
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,

        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 15,
            offset: const Offset(0, 5),
          ),
        ],
      ),

      child: IconButton(
        onPressed: onTap,
        icon: Icon(
          icon,
          color: const Color(0xFF1D1D1F),
        ),
      ),
    );
  }
}

// ============================================================
// BOTTOM NAV ITEM
// ============================================================

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,

      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),

        padding: const EdgeInsets.symmetric(
          horizontal: 13,
          vertical: 8,
        ),

        decoration: BoxDecoration(
          color: selected
              ? const Color(0xFF34C759).withOpacity(0.10)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(18),
        ),

        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [

            Icon(
              icon,
              size: 22,
              color: selected
                  ? const Color(0xFF34C759)
                  : const Color(0xFF8E8E93),
            ),

            const SizedBox(height: 3),

            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: selected
                    ? FontWeight.w700
                    : FontWeight.w500,
                color: selected
                    ? const Color(0xFF34C759)
                    : const Color(0xFF8E8E93),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// PLACEHOLDER SCREEN
// ============================================================

class PlaceholderScreen extends StatelessWidget {
  final String title;
  final IconData icon;

  const PlaceholderScreen({
    super.key,
    required this.title,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [

          Icon(
            icon,
            size: 50,
            color: const Color(0xFF34C759),
          ),

          const SizedBox(height: 15),

          Text(
            title,
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w700,
            ),
          ),

          const SizedBox(height: 6),

          const Text(
            'Coming soon',
            style: TextStyle(
              color: Color(0xFF8E8E93),
            ),
          ),
        ],
      ),
    );
  }
}