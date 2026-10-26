/*
 * Copyright (C) 2022 Open Source Robotics Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

// Vannmotstand med strøm. Kopi av vrx::SimpleHydrodynamics fra VRX (vrx_gz/src/SimpleHydrodynamics.cc,
// humble-grenen), med én endring: motstand og Coriolis regnes ut fra farten gjennom vannet
// (båtens fart minus strømmen) i stedet for farten over grunnen. Uten strøm er den lik VRX sin.
//
// Parametre som i SimpleHydrodynamics (Fossen), pluss:
//   <current_speed>      strømfart i m/s (standard 0)
//   <current_direction>  retningen strømmen går mot, i grader i verden: 0 = mot øst, 90 = mot nord

#include <cmath>
#include <memory>
#include <string>

#include <Eigen/Eigen>
#include <gz/common/Profiler.hh>
#include <gz/math/Vector3.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <sdf/sdf.hh>

namespace asv
{

class CurrentHydrodynamics
    : public gz::sim::System,
      public gz::sim::ISystemConfigure,
      public gz::sim::ISystemPreUpdate
{
  public: void Configure(const gz::sim::Entity &_entity,
                         const std::shared_ptr<const sdf::Element> &_sdf,
                         gz::sim::EntityComponentManager &_ecm,
                         gz::sim::EventManager &) override
  {
    gz::sim::Model model(_entity);
    if (!_sdf->HasElement("link_name"))
    {
      gzerr << "No <link_name> specified" << std::endl;
      return;
    }
    const auto linkName = _sdf->Get<std::string>("link_name");
    this->link = gz::sim::Link(model.LinkByName(_ecm, linkName));
    if (!this->link.Valid(_ecm))
    {
      gzerr << "Could not find link named [" << linkName << "] in model" << std::endl;
      return;
    }
    this->link.EnableVelocityChecks(_ecm);
    this->link.EnableAccelerationChecks(_ecm);

    // Samme standardverdier som SimpleHydrodynamics.
    this->xDotU = _sdf->Get<double>("xDotU", 5).first;
    this->yDotV = _sdf->Get<double>("yDotV", 5).first;
    const double zDotW = _sdf->Get<double>("zDotW", 0.1).first;
    const double kDotP = _sdf->Get<double>("kDotP", 0.1).first;
    const double mDotQ = _sdf->Get<double>("mDotQ", 0.1).first;
    const double nDotR = _sdf->Get<double>("nDotR", 1).first;
    this->xU = _sdf->Get<double>("xU", 20).first;
    this->xUU = _sdf->Get<double>("xUU", 0).first;
    this->yV = _sdf->Get<double>("yV", 20).first;
    this->yVV = _sdf->Get<double>("yVV", 0).first;
    this->zW = _sdf->Get<double>("zW", 20).first;
    this->zWW = _sdf->Get<double>("zWW", 0).first;
    this->kP = _sdf->Get<double>("kP", 20).first;
    this->kPP = _sdf->Get<double>("kPP", 0).first;
    this->mQ = _sdf->Get<double>("mQ", 20).first;
    this->mQQ = _sdf->Get<double>("mQQ", 0).first;
    this->nR = _sdf->Get<double>("nR", 20).first;
    this->nRR = _sdf->Get<double>("nRR", 0).first;

    // Added mass according to Fossen's equations (p 37).
    this->Ma = Eigen::MatrixXd::Zero(6, 6);
    this->Ma.diagonal() << this->xDotU, this->yDotV, zDotW, kDotP, mDotQ, nDotR;

    const double speed = _sdf->Get<double>("current_speed", 0.0).first;
    const double direction = _sdf->Get<double>("current_direction", 0.0).first * M_PI / 180.0;
    this->current = gz::math::Vector3d(speed * std::cos(direction), speed * std::sin(direction), 0);
    gzmsg << "CurrentHydrodynamics: strøm " << this->current << " m/s (verden)" << std::endl;
  }

  public: void PreUpdate(const gz::sim::UpdateInfo &_info,
                         gz::sim::EntityComponentManager &_ecm) override
  {
    GZ_PROFILE("CurrentHydrodynamics::PreUpdate");
    if (_info.paused || !this->link.Valid(_ecm))
      return;

    const auto worldAngularVel = this->link.WorldAngularVelocity(_ecm);
    const auto worldLinearVel = this->link.WorldLinearVelocity(_ecm);
    const auto worldAngularAccel = this->link.WorldAngularAcceleration(_ecm);
    const auto worldLinearAccel = this->link.WorldLinearAcceleration(_ecm);
    if (!worldAngularVel || !worldLinearVel || !worldAngularAccel || !worldLinearAccel)
    {
      gzerr << "Missing velocity or acceleration of the link" << std::endl;
      return;
    }

    // Transform from world to local frame. Den eneste endringen fra SimpleHydrodynamics: farten
    // gjennom vannet (minus strømmen) brukes for motstand og Coriolis.
    const auto comPose = this->link.WorldInertialPose(_ecm);
    const auto rotInv = comPose->Rot().Inverse();
    const auto localAngularVel = rotInv * (*worldAngularVel);
    const auto localLinearVel = rotInv * (*worldLinearVel - this->current);
    const auto localAngularAccel = rotInv * (*worldAngularAccel);
    const auto localLinearAccel = rotInv * (*worldLinearAccel);

    Eigen::VectorXd stateDot(6);
    Eigen::VectorXd state(6);
    stateDot << localLinearAccel.X(), localLinearAccel.Y(), localLinearAccel.Z(),
      localAngularAccel.X(), localAngularAccel.Y(), localAngularAccel.Z();
    state << localLinearVel.X(), localLinearVel.Y(), localLinearVel.Z(),
      localAngularVel.X(), localAngularVel.Y(), localAngularVel.Z();

    // Added Mass.
    const Eigen::VectorXd kAmassVec = -1.0 * this->Ma * stateDot;

    // Drag.
    Eigen::MatrixXd Dmat = Eigen::MatrixXd::Zero(6, 6);
    Dmat(0, 0) = this->xU + this->xUU * std::abs(localLinearVel.X());
    Dmat(1, 1) = this->yV + this->yVV * std::abs(localLinearVel.Y());
    Dmat(2, 2) = this->zW + this->zWW * std::abs(localLinearVel.Z());
    Dmat(3, 3) = this->kP + this->kPP * std::abs(localAngularVel.X());
    Dmat(4, 4) = this->mQ + this->mQQ * std::abs(localAngularVel.Y());
    Dmat(5, 5) = this->nR + this->nRR * std::abs(localAngularVel.Z());
    const Eigen::VectorXd kDvec = -1.0 * Dmat * state;

    // Sum all forces - in body frame. (Cmat i SimpleHydrodynamics regnes ut, men brukes ikke der
    // heller, så den er utelatt.)
    const Eigen::VectorXd kForceSum = kAmassVec + kDvec;

    // Transform the force and torque to the world frame and apply at COM.
    const auto forceWorld = comPose->Rot().RotateVector(
      gz::math::Vector3d(kForceSum(0), kForceSum(1), kForceSum(2)));
    const auto torqueWorld = comPose->Rot().RotateVector(
      gz::math::Vector3d(kForceSum(3), kForceSum(4), kForceSum(5)));
    this->link.AddWorldWrench(_ecm, forceWorld, torqueWorld);
  }

  private: gz::sim::Link link{gz::sim::kNullEntity};
  private: gz::math::Vector3d current;
  private: Eigen::MatrixXd Ma;
  private: double xDotU{0}, yDotV{0};
  private: double xU{0}, xUU{0}, yV{0}, yVV{0}, zW{0}, zWW{0};
  private: double kP{0}, kPP{0}, mQ{0}, mQQ{0}, nR{0}, nRR{0};
};

}  // namespace asv

GZ_ADD_PLUGIN(asv::CurrentHydrodynamics,
              gz::sim::System,
              asv::CurrentHydrodynamics::ISystemConfigure,
              asv::CurrentHydrodynamics::ISystemPreUpdate)
GZ_ADD_PLUGIN_ALIAS(asv::CurrentHydrodynamics, "asv::CurrentHydrodynamics")
